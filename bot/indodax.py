"""Klien API publik Indodax (tanpa API key) dengan timeout dan retry terbatas."""
import json
import time
import urllib.error
import urllib.request

from bot import config as C

BASE = "https://indodax.com"
UA = "indodax-dryrun-uas/1.0 (public API, dry run)"


class ApiError(Exception):
    pass


def get_json(path, errors=None, retries=None):
    """GET dengan retry terbatas. Setiap kegagalan dicatat ke list `errors`."""
    url = BASE + path
    retries = C.HTTP_MAX_RETRIES if retries is None else retries
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=C.HTTP_TIMEOUT_S) as r:
                body = r.read()
            if not body:
                raise ApiError("respons kosong")
            data = json.loads(body)
            if data in (None, [], {}):
                raise ApiError("respons JSON kosong")
            if isinstance(data, dict) and data.get("error"):
                raise ApiError(f"error API: {data.get('error')}")
            return data
        except (urllib.error.URLError, TimeoutError, ValueError, ApiError, OSError) as e:
            last = e
            if errors is not None:
                errors.append({"url": path, "attempt": attempt, "error": f"{type(e).__name__}: {e}"})
            if attempt < retries:
                time.sleep(C.HTTP_BACKOFF_S * attempt)
    raise ApiError(f"gagal setelah {retries} percobaan: {path}: {last}")


def server_time(errors=None):
    return int(get_json("/api/server_time", errors)["server_time"]) // 1000


def depth(symbol, errors=None):
    d = get_json(f"/api/depth/{symbol.lower()}", errors)
    bids = [[float(p), float(q)] for p, q in d.get("buy", [])]
    asks = [[float(p), float(q)] for p, q in d.get("sell", [])]
    bids.sort(key=lambda x: -x[0])
    asks.sort(key=lambda x: x[0])
    return {"bids": bids, "asks": asks}


def history(symbol, tf, frm, to, errors=None):
    d = get_json(f"/tradingview/history_v2?symbol={symbol}&tf={tf}&from={int(frm)}&to={int(to)}", errors)
    out = []
    for c in d:
        out.append({"Time": int(c["Time"]), "Open": float(c["Open"]), "High": float(c["High"]),
                    "Low": float(c["Low"]), "Close": float(c["Close"]), "Volume": float(c["Volume"])})
    out.sort(key=lambda c: c["Time"])
    return out


def closed_only(candles, now_ts, tf_seconds):
    """Buang setiap bar dengan Time + durasi > server_time (candle berjalan)."""
    return [c for c in candles if c["Time"] + tf_seconds <= now_ts]
