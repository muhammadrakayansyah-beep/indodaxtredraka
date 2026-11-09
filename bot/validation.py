"""Validasi data. Dipakai bot dan backtest (pemeriksaan candle yang sama)."""
from bot import config as C


def window_problems(window, now_ts=None):
    """Masalah pada jendela indikator. `now_ts` None -> lewati cek basi (backtest)."""
    probs = []
    if len(window) < C.INDICATOR_WINDOW:
        probs.append(f"candle kurang: {len(window)} < {C.INDICATOR_WINDOW}")
        return probs
    for a, b in zip(window, window[1:]):
        if b["Time"] - a["Time"] != C.TF_SECONDS:
            probs.append(f"candle hilang/tidak urut antara {a['Time']} dan {b['Time']}")
            break
    for c in window:
        if min(c["Open"], c["High"], c["Low"], c["Close"]) <= 0:
            probs.append(f"harga nol/negatif pada {c['Time']}")
            break
    # Volume nol dicek pada candle keputusan saja. Data Indodax asli memuat candle
    # bervolume 0 (mis. 2024-09-12 di semua pair); memblokir seluruh jendela 300 candle
    # karena satu hari itu akan mematikan strategi ~300 hari. Lihat STRATEGI.md.
    if window[-1]["Volume"] <= 0:
        probs.append(f"volume nol pada candle keputusan {window[-1]['Time']}")
    if now_ts is not None:
        age = now_ts - (window[-1]["Time"] + C.TF_SECONDS)
        if age > C.STALE_FACTOR * C.TF_SECONDS:
            probs.append(f"candle tertutup terakhir basi: umur {age}s > {C.STALE_FACTOR}x timeframe")
    return probs


def book_problems(stats):
    if stats is None:
        return ["order book kosong"]
    if stats["best_bid"] <= 0 or stats["best_ask"] <= 0:
        return ["harga order book nol"]
    if stats["best_ask"] <= stats["best_bid"]:
        return ["order book terkunci/terbalik (ask <= bid)"]
    if stats["spread_pct"] > C.MAX_SPREAD_PCT:
        return [f"spread {stats['spread_pct']:.4%} > {C.MAX_SPREAD_PCT:.0%}"]
    return []
