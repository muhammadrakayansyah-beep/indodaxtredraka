"""Satu panggilan bot (/api/tick): baca state -> ambil data -> sinyal -> eksekusi
simulasi -> simpan state & log. Dirancang aman dipanggil berulang (idempotent)."""
import hashlib
import json
import os
import time
import uuid

from bot import config as C
from bot import execution as X
from bot import indodax as API
from bot import strategy as S
from bot import validation as V
from bot.timeutil import iso, wib_day

TRUTHY = {"1", "true", "on", "yes"}


def new_state():
    return {
        "version": C.STRATEGY_VERSION,
        "cash": C.INITIAL_CAPITAL_IDR,
        "positions": {},          # pair -> posisi
        "last_processed": {},     # pair -> Time candle terakhir yang diproses
        "day": None,
        "day_start_equity": None,
        "daily_halt": False,
        "kill_switch_last": False,
        "last_bid": {},
        "created_at": None,
    }


def window_digest(window):
    raw = json.dumps([[c["Time"], c["Open"], c["High"], c["Low"], c["Close"], c["Volume"]] for c in window],
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def kill_switch_on(store):
    env = os.environ.get("KILL_SWITCH", "").strip().lower() in TRUTHY
    try:
        v = store.get("kill_switch")
    except Exception:  # storage error -> fail safe: anggap aktif
        return True, "storage_error"
    red = str(v or "").strip().lower() in TRUTHY
    src = "env" if env else ("redis" if red else "")
    return env or red, src


def equity_of(state):
    eq = state["cash"]
    for pair, p in state["positions"].items():
        eq += p["qty"] * state["last_bid"].get(pair, 0.0)
    return eq


def run_tick(store, trigger="unknown", now_fn=time.time):
    t0 = now_fn()
    call_id = uuid.uuid4().hex[:12]
    logs, errors = [], []
    call = {"call_id": call_id, "ts_wall": iso(t0), "ts_wall_unix": int(t0), "trigger": trigger,
            "version": C.STRATEGY_VERSION}

    if not store.acquire_lock(call_id):
        call.update(status="skipped_locked", duration_s=round(now_fn() - t0, 3))
        store.append_many([("calls", call)])
        return call

    try:
        raw = store.get("state")
        state = json.loads(raw) if raw else new_state()
        if state.get("created_at") is None:
            state["created_at"] = iso(t0)
            logs.append(("events", {"ts": iso(t0), "call_id": call_id, "type": "state_init",
                                    "cash": state["cash"]}))

        # --- waktu server (wajib untuk membuang candle yang masih berjalan)
        try:
            now = API.server_time(errors)
        except API.ApiError as e:
            call.update(status="error_server_time", error=str(e))
            raise
        call["server_time"] = iso(now)
        call["server_time_unix"] = now

        # --- kill switch
        ks, ks_src = kill_switch_on(store)
        call["kill_switch"] = ks
        if ks != state.get("kill_switch_last", False):
            logs.append(("events", {"ts": iso(now), "call_id": call_id,
                                    "type": "kill_switch_on" if ks else "kill_switch_off", "source": ks_src}))
            state["kill_switch_last"] = ks
        if ks:
            logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "kill_switch_active",
                                    "source": ks_src, "effect": "entry diblokir, exit tetap"}))

        # --- order book semua pair + snapshot mentah
        books, stats = {}, {}
        for pair in C.UNIVERSE:
            try:
                b = API.depth(pair, errors)
            except API.ApiError as e:
                logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "data_invalid",
                                        "pair": pair, "reasons": [f"depth gagal: {e}"]}))
                continue
            books[pair] = b
            st = X.book_stats(b)
            stats[pair] = st
            logs.append(("snapshots", {"ts": iso(now), "ts_unix": now, "call_id": call_id, "pair": pair,
                                       "bids": b["bids"][:C.ORDERBOOK_LEVELS_TO_STORE],
                                       "asks": b["asks"][:C.ORDERBOOK_LEVELS_TO_STORE]}))
            if st:
                state["last_bid"][pair] = st["best_bid"]

        # --- equity harian (panggilan pertama setelah 00:00 WIB) & daily loss limit
        eq = equity_of(state)
        day = wib_day(now)
        if state["day"] != day:
            state["day"] = day
            state["day_start_equity"] = eq
            state["daily_halt"] = False
            logs.append(("equity_daily", {"day_wib": day, "ts": iso(now), "call_id": call_id, "equity": eq,
                                          "cash": state["cash"],
                                          "positions": {k: v["qty"] for k, v in state["positions"].items()},
                                          "marked_at": "best_bid"}))
        if not state["daily_halt"] and eq < state["day_start_equity"] * (1 - C.DAILY_LOSS_LIMIT):
            state["daily_halt"] = True
            logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "daily_loss_limit_hit",
                                    "equity": eq, "day_start_equity": state["day_start_equity"]}))

        processed = {}
        for pair in C.UNIVERSE:
            processed[pair] = _process_pair(pair, state, books.get(pair), stats.get(pair), now, call_id,
                                            ks, logs, errors)

        call["processed"] = processed
        call["equity"] = equity_of(state)
        call["cash"] = state["cash"]
        call["open_positions"] = len(state["positions"])
        call["daily_halt"] = state["daily_halt"]
        call["status"] = call.get("status", "ok")
        store.set("state", json.dumps(state))
    except Exception as e:  # noqa: BLE001 - semua error dicatat
        call.setdefault("status", "error")
        call["error"] = f"{type(e).__name__}: {e}"
    finally:
        call["api_errors"] = len(errors)
        call["duration_s"] = round(now_fn() - t0, 3)
        for e in errors:
            e.update(call_id=call_id, ts=iso(t0))
            logs.append(("errors", e))
        logs.append(("calls", call))
        try:
            store.append_many(logs)
        finally:
            store.release_lock(call_id)
    return call


def _process_pair(pair, state, book, st, now, call_id, ks, logs, errors):
    pos = state["positions"].get(pair)

    # exit tertunda (book kosong/partial sebelumnya) dicoba lagi tiap panggilan
    if pos and pos.get("pending_exit") and book:
        _sell(pair, state, book, st, now, call_id, pos["pending_exit"], pos.get("pending_signal_price"),
              pos.get("pending_candle_time"), logs)
        pos = state["positions"].get(pair)

    try:
        frm = now - (C.INDICATOR_WINDOW + 40) * C.TF_SECONDS
        candles = API.history(pair, C.TIMEFRAME, frm, now, errors)
    except API.ApiError as e:
        logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "data_invalid", "pair": pair,
                                "reasons": [f"history gagal: {e}"]}))
        return "history_error"
    closed = API.closed_only(candles, now, C.TF_SECONDS)
    if not closed:
        logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "data_invalid", "pair": pair,
                                "reasons": ["tidak ada candle tertutup"]}))
        return "no_closed_candle"
    last_t = closed[-1]["Time"]
    prev_t = state["last_processed"].get(pair)

    # idempotency: setiap candle hanya diproses sekali
    if prev_t is not None and last_t <= prev_t:
        return f"dup:{iso(last_t)}"
    if prev_t is not None and last_t - prev_t > C.TF_SECONDS:
        missed = list(range(prev_t + C.TF_SECONDS, last_t, C.TF_SECONDS))
        logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "missed_candles", "pair": pair,
                                "candles": [iso(t) for t in missed]}))

    window = closed[-C.INDICATOR_WINDOW:]
    probs = V.window_problems(window, now)
    if probs:
        logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "data_invalid", "pair": pair,
                                "candle_time": iso(last_t), "reasons": probs}))
        logs.append(("signals", {"ts": iso(now), "call_id": call_id, "pair": pair, "candle_time": last_t,
                                 "action": "INVALID", "reason": "; ".join(probs)}))
        return "invalid_data"

    position_in = None
    if pos:
        position_in = {"signal_time": pos["signal_time"], "ref_price": pos.get("ref_price")}
    dec = S.evaluate(window, position_in)
    if pos and dec.get("ref_price") is not None:
        pos["ref_price"] = dec["ref_price"]

    sig = {"ts": iso(now), "ts_unix": now, "call_id": call_id, "pair": pair, "candle_time": last_t,
           "candle_close_time": last_t + C.TF_SECONDS, "delay_s": now - (last_t + C.TF_SECONDS),
           "action": dec["action"], "reason": dec["reason"], "ind": dec["ind"],
           "bars_held": dec.get("bars_held"), "ref_price": dec.get("ref_price"),
           "had_position": pos is not None, "window_digest": window_digest(window),
           "last_candle": window[-1], "executed": False}

    if dec["action"] == "BUY":
        blocked = []
        if ks:
            blocked.append("kill_switch")
        if state["daily_halt"]:
            blocked.append("daily_loss_limit")
        if len(state["positions"]) >= C.MAX_OPEN_POSITIONS:
            blocked.append("max_open_positions")
        if book is None:
            blocked.append("order book tidak tersedia")
        else:
            blocked += V.book_problems(st)
        if not blocked:
            res = _buy(pair, state, book, st, now, call_id, dec, logs)
            if isinstance(res, str):
                blocked.append(res)
            else:
                sig["executed"] = True
        sig["blocked"] = blocked
        if blocked:
            logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "entry_blocked", "pair": pair,
                                    "candle_time": iso(last_t), "reasons": blocked}))
    elif dec["action"] == "SELL":
        if book is None or st is None:
            pos.update(pending_exit=dec["reason"], pending_signal_price=dec["ind"]["close"],
                       pending_candle_time=last_t)
            sig["blocked"] = ["order book kosong; exit ditunda"]
        else:
            if st["spread_pct"] > C.MAX_SPREAD_PCT:
                logs.append(("events", {"ts": iso(now), "call_id": call_id, "type": "wide_spread_exit",
                                        "pair": pair, "spread_pct": st["spread_pct"]}))
            _sell(pair, state, book, st, now, call_id, dec["reason"], dec["ind"]["close"], last_t, logs)
            sig["executed"] = True

    logs.append(("signals", sig))
    state["last_processed"][pair] = last_t
    return f"processed:{iso(last_t)}:{dec['action']}"


def _order_record(pair, side, now, call_id, st, fill, fee, signal_price, candle_time, extra):
    rec = {"ts": iso(now), "ts_unix": now, "call_id": call_id, "pair": pair, "side": side,
           "qty": fill["qty"], "best_bid": st["best_bid"], "best_ask": st["best_ask"], "mid": st["mid"],
           "avg_fill": fill["vwap"], "notional": fill["notional"], "fee": fee, "fee_rate": C.TAKER_FEE,
           "levels_used": fill["levels"], "signal_price": signal_price,
           "signal_candle_time": candle_time,
           "diff_vs_signal_pct": (fill["vwap"] - signal_price) / signal_price if signal_price else None,
           "spread_slip_cost_idr": abs(fill["vwap"] - st["mid"]) * fill["qty"]}
    rec.update(extra)
    return rec


def _buy(pair, state, book, st, now, call_id, dec, logs):
    eq = equity_of(state)
    budget = min(C.MAX_POSITION_FRACTION * eq, state["cash"]) / (1 + C.TAKER_FEE)
    if budget < C.MIN_ORDER_IDR:
        return f"ukuran order {budget:.0f} < minimum {C.MIN_ORDER_IDR:.0f}"
    fill = X.sweep_buy_idr(book["asks"], budget)
    if fill is None or fill["notional"] < C.MIN_ORDER_IDR:
        return "fill di bawah minimum / kedalaman tidak cukup"
    fee = fill["notional"] * C.TAKER_FEE
    state["cash"] -= fill["notional"] + fee
    state["positions"][pair] = {"qty": fill["qty"], "entry_vwap": fill["vwap"], "entry_cost": fill["notional"] + fee,
                                "entry_fee": fee, "entry_mid": st["mid"], "entry_ts": iso(now),
                                "signal_time": dec["candle_time"], "ref_price": None}
    rec = _order_record(pair, "BUY", now, call_id, st, fill, fee, dec["ind"]["close"], dec["candle_time"],
                        {"reason": dec["reason"], "unfilled_idr": fill["unfilled_idr"]})
    state["positions"][pair]["entry_spread_cost"] = rec["spread_slip_cost_idr"]
    logs.append(("orders", rec))
    return fill


def _sell(pair, state, book, st, now, call_id, reason, signal_price, candle_time, logs):
    pos = state["positions"][pair]
    fill = X.sweep_sell_qty(book["bids"], pos["qty"])
    if fill is None:
        pos.update(pending_exit=reason, pending_signal_price=signal_price, pending_candle_time=candle_time)
        return None
    fee = fill["notional"] * C.TAKER_FEE
    frac = min(fill["qty"] / pos["qty"], 1.0)
    cost_alloc = pos["entry_cost"] * frac
    pnl = fill["notional"] - fee - cost_alloc
    gross = (st["mid"] - pos["entry_mid"]) * fill["qty"]
    state["cash"] += fill["notional"] - fee
    logs.append(("orders", _order_record(pair, "SELL", now, call_id, st, fill, fee, signal_price, candle_time, {
        "reason": reason, "entry_vwap": pos["entry_vwap"], "entry_ts": pos["entry_ts"],
        "realized_pnl": pnl, "gross_pnl_mid": gross, "entry_fee_alloc": pos["entry_fee"] * frac,
        "entry_spread_cost_alloc": pos.get("entry_spread_cost", 0.0) * frac,
        "unfilled_qty": fill["unfilled_qty"]})))
    remaining = X.floor_qty(pos["qty"] - fill["qty"])
    if remaining > 0:
        pos["qty"] = remaining
        pos["entry_cost"] -= cost_alloc
        pos["entry_fee"] -= pos["entry_fee"] * frac
        pos["entry_spread_cost"] = pos.get("entry_spread_cost", 0.0) * (1 - frac)
        pos.update(pending_exit=reason, pending_signal_price=signal_price, pending_candle_time=candle_time)
    else:
        del state["positions"][pair]
    return fill
