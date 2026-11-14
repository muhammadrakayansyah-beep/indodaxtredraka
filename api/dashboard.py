"""GET /api/dashboard — dashboard publik read-only yang membaca log dari storage
dan menghitung angka dengan fungsi yang sama dengan scripts/hitung_ulang.py."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import time  # noqa: E402
from http.server import BaseHTTPRequestHandler  # noqa: E402

from bot import config as C
from bot import indodax as API
from bot import metrics as M
from bot import report as R
from bot import storage
from bot.metrics import forward_window


def _load_json(rel):
    p = os.path.join(ROOT, rel)
    return json.load(open(p)) if os.path.exists(p) else None


def build():
    store = storage.from_env()
    raw = {s: store.read_stream(s) for s in storage.STREAMS}
    calib_doc = _load_json("data/calibration.json")
    calib = calib_doc["pairs"] if calib_doc and calib_doc.get("valid") else None
    bt_full = _load_json("data/backtest_full.json")
    now = API.server_time()
    start, end = forward_window()
    candles = {}
    if calib:
        to = min(now, end + C.TF_SECONDS)
        frm = start - (C.INDICATOR_WINDOW + 40) * C.TF_SECONDS
        for p in C.UNIVERSE:
            candles[p] = API.closed_only(API.history(p, C.TIMEFRAME, frm, to), now, C.TF_SECONDS)
            time.sleep(0.4)
    bt_orders = M.load_backtest_orders(os.path.join(ROOT, "data", "backtest_full_orders.csv"))
    D = M.compute_all(raw, candles, calib, bt_full, now, bt_orders)
    return R.render(D)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body, code = build().encode(), 200
        except Exception as e:  # noqa: BLE001
            body, code = f"<h1>Dashboard error</h1><pre>{type(e).__name__}: {e}</pre>".encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "s-maxage=300")
        self.end_headers()
        self.wfile.write(body)
