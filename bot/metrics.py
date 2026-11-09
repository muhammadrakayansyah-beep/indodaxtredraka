"""Semua angka dashboard dihitung di sini dari log mentah + candle Indodax.
Dipakai oleh scripts/hitung_ulang.py (offline) dan api/dashboard.py (Vercel),
sehingga kedua dashboard memakai rumus yang identik."""
import statistics

from bot import backtest_core as BT
from bot import config as C
from bot import execution as X
from bot.timeutil import iso, parse_iso


def max_drawdown(values):
    peak, mdd = None, 0.0
    for v in values:
        peak = v if peak is None or v > peak else peak
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return mdd


def cagr(start_v, end_v, seconds):
    years = seconds / (365.25 * 86400)
    if years <= 0 or start_v <= 0 or end_v <= 0:
        return None
    return (end_v / start_v) ** (1 / years) - 1


def trade_stats(trades):
    """trades: list dict dengan realized_pnl, gross_pnl_mid, fees, spread_slip_cost."""
    wins = [t["realized_pnl"] for t in trades if t["realized_pnl"] > 0]
    losses = [t["realized_pnl"] for t in trades if t["realized_pnl"] <= 0]
    fees = sum(t["fees"] for t in trades)
    ss = sum(t["spread_slip_cost"] for t in trades)
    gross = sum(t["gross_pnl_mid"] for t in trades)
    return {
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) if trades else None,
        "profit_factor": (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0
        else ("tak_hingga_tanpa_rugi" if wins else None),
        "avg_win": sum(wins) / len(wins) if wins else None,
        "avg_loss": sum(losses) / len(losses) if losses else None,
        "fees_idr": fees,
        "spread_slippage_idr": ss,
        "gross_profit_idr": gross,
        "cost_share_of_gross": (fees + ss) / gross if gross > 0 else None,
        "cost_share_note": None if gross > 0 else "laba kotor <= 0 atau tidak ada trade: rasio tidak terdefinisi",
    }


def backtest_trades(orders):
    out = []
    for o in orders:
        if o["side"] == "SELL":
            out.append({"realized_pnl": o["realized_pnl"], "gross_pnl_mid": o["gross_pnl_mid"],
                        "fees": o["entry_fee_alloc"] + o["exit_fee"], "spread_slip_cost": o["spread_slip_cost"]})
    return out


def live_trades(orders):
    out = []
    for o in orders:
        if o["side"] == "SELL":
            out.append({"realized_pnl": o["realized_pnl"], "gross_pnl_mid": o["gross_pnl_mid"],
                        "fees": o["entry_fee_alloc"] + o["fee"],
                        "spread_slip_cost": o.get("entry_spread_cost_alloc", 0.0) + o["spread_slip_cost_idr"],
                        "pair": o["pair"], "ts": o["ts"], "reason": o.get("reason")})
    return out


def summarize_backtest(res, candles, calib, eval_from, eval_to, with_cagr=True):
    eq = [e["equity"] for e in res["equity"]]
    out = {"eval_from": iso(eval_from), "eval_to": iso(eval_to), "capital": res["capital"],
           "final_equity": res["final_equity"], "total_return": res["final_equity"] / res["capital"] - 1,
           "max_drawdown": max_drawdown([res["capital"]] + eq),
           "open_positions_at_end": sorted(res["open_positions"].keys())}
    if with_cagr and res["equity"]:
        out["cagr"] = cagr(res["capital"], res["final_equity"],
                           res["equity"][-1]["time"] + C.TF_SECONDS - res["equity"][0]["time"])
    out.update(trade_stats(backtest_trades(res["orders"])))
    bh = BT.benchmark_buy_hold(candles[C.BENCHMARK_SYMBOL], calib[C.BENCHMARK_SYMBOL], eval_from, eval_to)
    out["benchmark_btc_buy_hold"] = {"total_return": bh["total_return"]} if bh else None
    out["equity_curve"] = res["equity"]
    return out


def in_window(rec, start, end, key="ts"):
    t = parse_iso(rec[key])
    return start <= t <= end


def forward_window():
    return parse_iso(C.FORWARD_START_UTC), parse_iso(C.FORWARD_END_UTC)


def forward_candle_times(start, end):
    """Candle harian yang ditutup di dalam jendela forward: start < Time+tf <= end."""
    first = ((start // C.TF_SECONDS) * C.TF_SECONDS)  # candle yang ditutup pertama setelah start
    out = []
    t = first
    while t + C.TF_SECONDS <= end:
        if t + C.TF_SECONDS > start:
            out.append(t)
        t += C.TF_SECONDS
    return out


def uptime(signals, start, end, now_ts):
    """Candle terproses tepat waktu (sinyal valid tercatat untuk semua pair sebelum candle
    berikutnya ditutup) / jumlah candle forward yang sudah ditutup."""
    cts = [t for t in forward_candle_times(start, end) if t + C.TF_SECONDS <= now_ts]
    rows, ok = [], 0
    for t in cts:
        deadline = t + 2 * C.TF_SECONDS
        per_pair = {}
        for p in C.UNIVERSE:
            hits = [s for s in signals if s["pair"] == p and s["candle_time"] == t and s["action"] != "INVALID"]
            on_time = [s for s in hits if s["ts_unix"] < deadline]
            per_pair[p] = "tepat_waktu" if on_time else ("terlambat" if hits else "tidak_diproses")
        good = all(v == "tepat_waktu" for v in per_pair.values())
        ok += good
        rows.append({"candle_time": iso(t), "closes_at": iso(t + C.TF_SECONDS), "deadline": iso(deadline),
                     "ok": good, "per_pair": per_pair})
    return {"candles_scheduled": len(cts), "candles_on_time": ok,
            "uptime": ok / len(cts) if cts else None, "rows": rows}


def snapshot_costs(snapshots, cutoff_unix=None):
    """Median spread & slippage per pair dari snapshot mentah."""
    per = {}
    for s in snapshots:
        if cutoff_unix is not None and s["ts_unix"] >= cutoff_unix:
            continue
        book = {"bids": s["bids"], "asks": s["asks"]}
        st = X.book_stats(book)
        if st is None:
            continue
        sl = X.slippage_for_ref_order(book)
        d = per.setdefault(s["pair"], {"spread": [], "buy": [], "sell": []})
        d["spread"].append(st["spread_pct"])
        if sl and sl["buy_slip_pct"] is not None:
            d["buy"].append(sl["buy_slip_pct"])
        if sl and sl["sell_slip_pct"] is not None:
            d["sell"].append(sl["sell_slip_pct"])
    out = {}
    for p, d in per.items():
        out[p] = {"n": len(d["spread"]),
                  "median_spread_pct": statistics.median(d["spread"]) if d["spread"] else None,
                  "half_spread": statistics.median(d["spread"]) / 2 if d["spread"] else None,
                  "buy_slip": statistics.median(d["buy"]) if d["buy"] else None,
                  "sell_slip": statistics.median(d["sell"]) if d["sell"] else None}
    return out


def compare_signals(live_signals, replay_signals, candle_times):
    """Bandingkan aksi sinyal candle demi candle."""
    ts = set(candle_times)
    live = {}
    for s in live_signals:
        if s["candle_time"] in ts and s["action"] != "INVALID":
            live.setdefault((s["pair"], s["candle_time"]), s)   # pemrosesan pertama
    rep = {(s["pair"], s["candle_time"]): s for s in replay_signals if "action" in s and s["candle_time"] in ts}
    rows, match, compared = [], 0, 0
    for p in C.UNIVERSE:
        for t in sorted(ts):
            l, r = live.get((p, t)), rep.get((p, t))
            row = {"pair": p, "candle_time": iso(t), "live": l["action"] if l else None,
                   "backtest": r["action"] if r else None,
                   "live_reason": l["reason"] if l else None, "backtest_reason": r["reason"] if r else None,
                   "live_had_position": l.get("had_position") if l else None,
                   "backtest_had_position": r.get("had_position") if r else None}
            if l and r:
                compared += 1
                row["match"] = l["action"] == r["action"]
                match += row["match"]
            else:
                row["match"] = None
            rows.append(row)
    return {"compared": compared, "matched": match, "match_rate": match / compared if compared else None,
            "rows": rows}


def fill_gaps(live_orders, same_window_orders):
    """Selisih harga fill live vs backtest per trade, diurai menjadi komponen."""
    bt = {(o["pair"], o["side"], o["signal_price"]): o for o in same_window_orders}
    rows = []
    for o in live_orders:
        r = {"pair": o["pair"], "side": o["side"], "ts": o["ts"], "signal_price": o["signal_price"],
             "best_bid": o["best_bid"], "best_ask": o["best_ask"], "avg_fill": o["avg_fill"],
             "spread_pct_at_fill": (o["best_ask"] - o["best_bid"]) / o["mid"],
             "slippage_vs_best_pct": ((o["avg_fill"] - o["best_ask"]) / o["best_ask"] if o["side"] == "BUY"
                                      else (o["best_bid"] - o["avg_fill"]) / o["best_bid"]),
             "delay_from_candle_close_s": o["ts_unix"] - (o["signal_candle_time"] + C.TF_SECONDS)
             if o.get("signal_candle_time") else None,
             "mid_move_vs_signal_pct": (o["mid"] - o["signal_price"]) / o["signal_price"],
             "diff_vs_signal_pct": o["diff_vs_signal_pct"]}
        b = bt.get((o["pair"], o["side"], o["signal_price"]))
        if b:
            r["backtest_fill"] = b["price"]
            r["backtest_open"] = b["open"]
            r["fill_gap_pct"] = (o["avg_fill"] - b["price"]) / b["price"]
        rows.append(r)
    return rows


def compute_all(raw, candles, calib, backtest_full, now_ts):
    """raw: {stream: [records]} log mentah. candles: {pair: [...]} dari Indodax yang
    mencakup jendela forward + INDICATOR_WINDOW. backtest_full: hasil scripts/backtest.py."""
    start, end = forward_window()
    calls = [c for c in raw.get("calls", []) if in_window(c, start, end, "ts_wall")]
    orders = [o for o in raw.get("orders", []) if in_window(o, start, end)]
    signals = [s for s in raw.get("signals", []) if in_window(s, start, end)]
    # catatan: sinyal untuk candle sebelum start yang diproses setelah start tetap ikut (berdasarkan ts proses)
    events = [e for e in raw.get("events", []) if in_window(e, start, end)]
    errors = [e for e in raw.get("errors", []) if in_window(e, start, end)]
    eq_daily = [e for e in raw.get("equity_daily", []) if in_window(e, start, end)]
    snaps = raw.get("snapshots", [])

    # ekuitas forward: setiap panggilan sukses (ditandai di best bid)
    eq_series = [{"ts": c["ts_wall"], "equity": c["equity"]} for c in calls if "equity" in c]
    cap = C.INITIAL_CAPITAL_IDR
    fwd = {"start": C.FORWARD_START_UTC, "end": C.FORWARD_END_UTC, "capital": cap,
           "final_equity": eq_series[-1]["equity"] if eq_series else None}
    fwd["total_return"] = fwd["final_equity"] / cap - 1 if eq_series else None
    fwd["max_drawdown"] = max_drawdown([cap] + [e["equity"] for e in eq_series]) if eq_series else None
    fwd.update(trade_stats(live_trades(orders)))
    fwd["open_orders_buy"] = sum(1 for o in orders if o["side"] == "BUY")

    # benchmark BTC buy & hold forward dari snapshot order book (ask awal, bid akhir)
    bs = [s for s in snaps if s["pair"] == C.BENCHMARK_SYMBOL and start <= s["ts_unix"] <= end
          and s["bids"] and s["asks"]]
    if len(bs) >= 2:
        a0, b1 = bs[0]["asks"][0][0], bs[-1]["bids"][0][0]
        fwd["benchmark_btc_buy_hold"] = {"total_return": b1 * (1 - C.TAKER_FEE) / (a0 * (1 + C.TAKER_FEE)) - 1,
                                         "from": bs[0]["ts"], "to": bs[-1]["ts"], "ask_start": a0, "bid_end": b1}
    else:
        fwd["benchmark_btc_buy_hold"] = None

    # replay backtest pada jendela & candle yang sama
    fct = [t for t in forward_candle_times(start, end) if t + C.TF_SECONDS <= now_ts]
    same = None
    sig_cmp = None
    if fct and candles and calib:
        # candle terakhir yang ditutup sebelum start juga diproses oleh panggilan pertama
        # bot setelah reset, jadi replay dimulai dari candle itu (lihat README).
        rep_from = fct[0] - C.TF_SECONDS
        res = BT.run(candles, calib, rep_from, fct[-1])
        same = summarize_backtest(res, candles, calib, rep_from, fct[-1], with_cagr=False)
        same.pop("cagr", None)
        sig_cmp = compare_signals(signals, res["signals"], [rep_from] + fct)
        same["orders"] = res["orders"]

    up = uptime(signals, start, end, now_ts)
    sched_hours = max(0, (min(end, now_ts) - start) // 3600)
    ops = {
        "calls_total": len(calls),
        "calls_ok": sum(1 for c in calls if c.get("status") == "ok"),
        "calls_error": sum(1 for c in calls if c.get("status", "").startswith("error")),
        "calls_skipped_locked": sum(1 for c in calls if c.get("status") == "skipped_locked"),
        "hourly_calls_expected": sched_hours,
        "api_errors": len(errors),
        "kill_switch_events": sum(1 for e in events if e["type"] in ("kill_switch_on", "kill_switch_off")),
        "kill_switch_active_calls": sum(1 for c in calls if c.get("kill_switch")),
        "daily_loss_limit_hits": sum(1 for e in events if e["type"] == "daily_loss_limit_hit"),
        "data_invalid_events": sum(1 for e in events if e["type"] == "data_invalid"),
        "entry_blocked_events": sum(1 for e in events if e["type"] == "entry_blocked"),
        "missed_candle_events": sum(1 for e in events if e["type"] == "missed_candles"),
        "bugfix_events": [e for e in events if e["type"] == "bugfix_note"],
        "call_delay_minutes": [round((c["ts_wall_unix"] % 3600) / 60, 1) for c in calls],
    }
    spread_cmp = {"calibration_used": calib,
                  "pre_freeze": snapshot_costs(snaps, start),
                  "all_snapshots": snapshot_costs(snaps)}
    gap = None
    if same and fwd["total_return"] is not None:
        gap = {"forward_minus_backtest_return": fwd["total_return"] - same["total_return"],
               "forward_minus_backtest_maxdd": fwd["max_drawdown"] - same["max_drawdown"],
               "trades_forward": fwd["trades"], "trades_backtest": same["trades"]}

    return {
        "generated_for_now": iso(now_ts),
        "strategy_version": C.STRATEGY_VERSION,
        "universe": C.UNIVERSE,
        "forward_complete": now_ts >= end,
        "backtest_full": {k: v for k, v in (backtest_full or {}).items() if k != "equity_curve"} or None,
        "backtest_full_curve": (backtest_full or {}).get("equity_curve_weekly"),
        "backtest_same_window": same,
        "forward": fwd,
        "forward_equity": eq_series,
        "forward_equity_daily": eq_daily,
        "gap": gap,
        "signal_match": sig_cmp,
        "fill_gaps": fill_gaps(orders, same["orders"] if same else []),
        "uptime": up,
        "ops": ops,
        "spread_comparison": spread_cmp,
        "orders": orders,
        "events_sample": events[-50:],
        "errors_sample": errors[-50:],
    }
