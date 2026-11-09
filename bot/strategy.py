"""Fungsi sinyal TUNGGAL yang dipakai backtest (scripts/backtest.py) dan bot
(bot/engine.py). Fungsi ini murni: input candle tertutup -> keputusan.
Tidak ada akses jaringan, waktu, atau state global di sini.
"""
from bot import config as C


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi_wilder(closes, period):
    """RSI Wilder: seed = rata-rata sederhana `period` perubahan pertama,
    lalu smoothing Wilder. Bergantung titik awal -> selalu dipanggil dengan
    jendela berpanjang tetap (INDICATOR_WINDOW)."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def indicators(window):
    """window: list candle dict (Time, Open, High, Low, Close, Volume) tertutup,
    urut naik, panjang tepat INDICATOR_WINDOW."""
    closes = [float(c["Close"]) for c in window]
    return {
        "close": closes[-1],
        "sma_fast": sma(closes, C.SMA_FAST),
        "sma_slow": sma(closes, C.SMA_SLOW),
        "sma_fast_prev": sma(closes[:-1], C.SMA_FAST),
        "sma_slow_prev": sma(closes[:-1], C.SMA_SLOW),
        "rsi": rsi_wilder(closes, C.RSI_PERIOD),
    }


def evaluate(window, position):
    """Kembalikan keputusan untuk candle terakhir di `window`.

    position: None (flat) atau dict
        {"signal_time": Time candle sinyal entry,
         "ref_price": Open candle setelah candle sinyal (atau None bila belum tersedia)}
    Harga referensi take-profit = Open candle setelah candle sinyal, sama
    seperti UTS (eksekusi open bar berikutnya). Nilai ini berasal dari data
    candle, bukan harga fill, sehingga backtest dan bot menghasilkan sinyal identik.
    """
    if len(window) != C.INDICATOR_WINDOW:
        raise ValueError(f"window harus {C.INDICATOR_WINDOW} candle, dapat {len(window)}")
    ind = indicators(window)
    t = int(window[-1]["Time"])
    out = {"candle_time": t, "action": "HOLD", "reason": "", "ind": ind}

    if position is None:
        if (ind["close"] > ind["sma_slow"] and ind["sma_fast"] > ind["sma_slow"]
                and ind["rsi"] < C.RSI_ENTRY_BELOW):
            out.update(action="BUY", reason="rsi<th & close>sma200 & sma50>sma200")
        return out

    bars_held = (t - int(position["signal_time"])) // C.TF_SECONDS
    out["bars_held"] = bars_held
    ref = position.get("ref_price")
    if ref is None:
        ref = next((float(c["Open"]) for c in window
                    if int(c["Time"]) == int(position["signal_time"]) + C.TF_SECONDS), None)
    out["ref_price"] = ref
    if ref is not None and ind["close"] >= ref * (1 + C.TAKE_PROFIT_PCT):
        out.update(action="SELL", reason="take_profit")
    elif ind["sma_fast_prev"] >= ind["sma_slow_prev"] and ind["sma_fast"] < ind["sma_slow"]:
        out.update(action="SELL", reason="death_cross")
    elif bars_held >= C.TIME_STOP_BARS:
        out.update(action="SELL", reason="time_stop")
    return out
