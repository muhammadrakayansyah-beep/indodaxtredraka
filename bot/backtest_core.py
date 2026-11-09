"""Mesin backtest. Memakai bot.strategy.evaluate (fungsi sinyal yang sama dengan bot)
dan bot.validation.window_problems.

Model eksekusi backtest (candle tidak punya bid/ask):
  - sinyal dihitung pada close candle t, dieksekusi pada Open candle t+1
    (bot live mengeksekusi ~15 menit setelah close pada order book saat itu);
  - beli  = Open * (1 + half_spread + buy_slip),  jual = Open * (1 - half_spread - sell_slip);
    half_spread & slip = median hasil pengukuran snapshot (data/calibration.json);
  - fee taker C.TAKER_FEE pada kedua sisi; minimum order C.MIN_ORDER_IDR;
  - ekuitas ditandai pada Close * (1 - half_spread) (proksi best bid);
  - daily loss limit: entry pada open t diblokir bila ekuitas close t-1 < 98% ekuitas
    close t-2 (aproksimasi; candle harian tidak punya titik 00:00 WIB).
"""
from bot import config as C
from bot import execution as X
from bot import strategy as S
from bot import validation as V


def run(candles, calib, eval_from, eval_to, capital=None, universe=None):
    """candles: {pair: [candle...]} urut naik. Sinyal dievaluasi untuk candle dengan
    eval_from <= Time <= eval_to. Mengembalikan dict hasil + log sinyal/order/equity."""
    universe = universe or C.UNIVERSE
    capital = C.INITIAL_CAPITAL_IDR if capital is None else capital
    idx = {p: {c["Time"]: i for i, c in enumerate(candles[p])} for p in universe}
    times = sorted({c["Time"] for p in universe for c in candles[p] if eval_from <= c["Time"] <= eval_to})
    cash = capital
    pos, pending = {}, {}   # pending[pair] = ("BUY"/"SELL", signal_close, reason, signal_time)
    signals, orders, equity = [], [], []
    last_close = {}
    eq_hist = []

    def mark():
        e = cash
        for p, q in pos.items():
            e += q["qty"] * last_close[p] * (1 - calib[p]["half_spread"])
        return e

    for t in times:
        # 1) eksekusi order tertunda pada Open candle t
        halted = len(eq_hist) >= 2 and eq_hist[-1] < eq_hist[-2] * (1 - C.DAILY_LOSS_LIMIT)
        eq_now = eq_hist[-1] if eq_hist else capital
        for p in universe:
            if p not in pending or t not in idx[p]:
                continue
            side, sig_px, reason, sig_t = pending.pop(p)
            o = candles[p][idx[p][t]]["Open"]
            cb = calib[p]
            if side == "BUY":
                blocked = []
                if halted:
                    blocked.append("daily_loss_limit")
                if len(pos) >= C.MAX_OPEN_POSITIONS:
                    blocked.append("max_open_positions")
                budget = min(C.MAX_POSITION_FRACTION * eq_now, cash) / (1 + C.TAKER_FEE)
                if budget < C.MIN_ORDER_IDR:
                    blocked.append("min_order")
                if blocked:
                    signals.append({"pair": p, "candle_time": sig_t, "exec_blocked": blocked})
                    continue
                px = o * (1 + cb["half_spread"] + cb["buy_slip"])
                qty = X.floor_qty(budget / px)
                notional = qty * px
                fee = notional * C.TAKER_FEE
                cash -= notional + fee
                pos[p] = {"qty": qty, "entry_px": px, "entry_cost": notional + fee, "entry_fee": fee,
                          "entry_open": o, "signal_time": sig_t, "ref_price": None,
                          "entry_spread_cost": (px - o) * qty, "entry_time": t}
                orders.append({"pair": p, "side": "BUY", "time": t, "price": px, "open": o, "qty": qty,
                               "fee": fee, "signal_price": sig_px, "reason": reason})
            else:
                q = pos.pop(p)
                px = o * (1 - cb["half_spread"] - cb["sell_slip"])
                proceeds = q["qty"] * px
                fee = proceeds * C.TAKER_FEE
                cash += proceeds - fee
                orders.append({"pair": p, "side": "SELL", "time": t, "price": px, "open": o, "qty": q["qty"],
                               "fee": fee, "signal_price": sig_px, "reason": reason,
                               "realized_pnl": proceeds - fee - q["entry_cost"],
                               "gross_pnl_mid": (o - q["entry_open"]) * q["qty"],
                               "entry_fee_alloc": q["entry_fee"], "exit_fee": fee,
                               "spread_slip_cost": q["entry_spread_cost"] + (o - px) * q["qty"],
                               "entry_time": q.get("entry_time", None)})
        # 2) evaluasi sinyal pada close candle t
        for p in universe:
            if t not in idx[p]:
                continue
            i = idx[p][t]
            last_close[p] = candles[p][i]["Close"]
            window = candles[p][max(0, i - C.INDICATOR_WINDOW + 1): i + 1]
            probs = V.window_problems(window)
            if probs:
                signals.append({"pair": p, "candle_time": t, "action": "INVALID", "reason": "; ".join(probs)})
                continue
            position_in = None
            if p in pos:
                position_in = {"signal_time": pos[p]["signal_time"], "ref_price": pos[p]["ref_price"]}
            d = S.evaluate(window, position_in)
            if p in pos and d.get("ref_price") is not None:
                pos[p]["ref_price"] = d["ref_price"]
            signals.append({"pair": p, "candle_time": t, "action": d["action"], "reason": d["reason"],
                            "had_position": p in pos, "rsi": d["ind"]["rsi"]})
            if d["action"] in ("BUY", "SELL"):
                pending[p] = (d["action"], d["ind"]["close"], d["reason"], t)
        e = mark()
        eq_hist.append(e)
        equity.append({"time": t, "equity": e})
    return {"signals": signals, "orders": orders, "equity": equity, "open_positions": pos,
            "final_equity": equity[-1]["equity"] if equity else capital, "capital": capital}


def benchmark_buy_hold(candles_btc, calib_btc, eval_from, eval_to, capital=None):
    capital = C.INITIAL_CAPITAL_IDR if capital is None else capital
    cs = [c for c in candles_btc if eval_from <= c["Time"] <= eval_to]
    if len(cs) < 2:
        return None
    cost = calib_btc["half_spread"] + calib_btc["buy_slip"]
    buy = cs[0]["Open"] * (1 + cost)
    sell = cs[-1]["Close"] * (1 - calib_btc["half_spread"] - calib_btc["sell_slip"])
    final = capital / (1 + C.TAKER_FEE) / buy * sell * (1 - C.TAKER_FEE)
    curve = [capital / (1 + C.TAKER_FEE) / buy * c["Close"] * (1 - calib_btc["half_spread"]) for c in cs]
    return {"total_return": final / capital - 1, "start": cs[0]["Time"], "end": cs[-1]["Time"],
            "curve": [{"time": c["Time"], "equity": v} for c, v in zip(cs, curve)]}
