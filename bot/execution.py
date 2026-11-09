"""Simulasi fill di order book: beli menyapu ask, jual menyapu bid.
Tidak pernah memakai mid atau close sebagai harga fill."""
import math

from bot import config as C


def floor_qty(q):
    f = 10 ** C.QTY_DECIMALS
    return math.floor(q * f + 1e-9) / f


def book_stats(book):
    bids, asks = book["bids"], book["asks"]
    if not bids or not asks:
        return None
    bb, ba = bids[0][0], asks[0][0]
    mid = (bb + ba) / 2
    return {"best_bid": bb, "best_ask": ba, "mid": mid, "spread_pct": (ba - bb) / mid}


def sweep_buy_idr(asks, idr_notional):
    """Beli senilai `idr_notional` (sebelum fee) dengan menyapu ask."""
    remaining, qty, cost, levels = idr_notional, 0.0, 0.0, 0
    for price, avail in asks:
        if remaining <= 1e-9:
            break
        take = min(avail, remaining / price)
        qty += take
        cost += take * price
        remaining -= take * price
        levels += 1
    qty_r = floor_qty(qty)
    if qty <= 0 or qty_r <= 0:
        return None
    # skala biaya ke kuantitas yang sudah dibulatkan (VWAP tetap)
    vwap = cost / qty
    return {"qty": qty_r, "vwap": vwap, "notional": qty_r * vwap, "levels": levels,
            "unfilled_idr": max(remaining, 0.0)}


def sweep_sell_qty(bids, qty):
    remaining, got, proceeds, levels = floor_qty(qty), 0.0, 0.0, 0
    for price, avail in bids:
        if remaining <= 1e-12:
            break
        take = min(avail, remaining)
        got += take
        proceeds += take * price
        remaining -= take
        levels += 1
    if got <= 0:
        return None
    return {"qty": floor_qty(got), "vwap": proceeds / got, "notional": proceeds, "levels": levels,
            "unfilled_qty": max(remaining, 0.0)}


def slippage_for_ref_order(book, idr=C.SLIPPAGE_REF_ORDER_IDR):
    """Slippage order referensi relatif terhadap best price (buy dan sell)."""
    s = book_stats(book)
    if s is None:
        return None
    b = sweep_buy_idr(book["asks"], idr)
    q = idr / s["best_bid"]
    sl = sweep_sell_qty(book["bids"], q)
    return {
        "buy_slip_pct": (b["vwap"] - s["best_ask"]) / s["best_ask"] if b and b["unfilled_idr"] < 1 else None,
        "sell_slip_pct": (s["best_bid"] - sl["vwap"]) / s["best_bid"] if sl and sl["unfilled_qty"] < 1e-9 else None,
    }
