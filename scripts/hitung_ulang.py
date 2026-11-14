"""Hitung ulang SEMUA angka dashboard dari log mentah (data/raw/*.jsonl) + candle Indodax.

  python scripts/hitung_ulang.py                 # hasilkan data/dashboard_data.json + dashboard.html
  python scripts/hitung_ulang.py --offline       # pakai data/candles/*.json (tanpa jaringan)
  python scripts/hitung_ulang.py --verify dashboard.html   # cocokkan angka HTML vs hitungan ulang
"""
import argparse
import glob
import json
import os
import sys
import time

import _lib
from bot import config as C
from bot import indodax as API
from bot import metrics as M
from bot import report as R
from bot import storage
from bot.timeutil import parse_iso


def load_raw():
    raw = {s: _lib.read_jsonl(_lib.p("data", "raw", f"{s}.jsonl")) for s in storage.STREAMS}
    for f in sorted(glob.glob(_lib.p("data", "raw", "snapshots_*.jsonl"))):
        raw["snapshots"] += _lib.read_jsonl(f)
    raw["snapshots"].sort(key=lambda s: s["ts_unix"])
    return raw


def load_candles(offline, now):
    start, end = M.forward_window()
    out = {}
    for p in C.UNIVERSE:
        if offline:
            out[p] = json.load(open(_lib.p("data", "candles", f"{p}_{C.TIMEFRAME}.json")))["candles"]
        else:
            frm = start - (C.INDICATOR_WINDOW + 40) * C.TF_SECONDS
            out[p] = API.closed_only(API.history(p, C.TIMEFRAME, frm, min(now, end + C.TF_SECONDS)), now, C.TF_SECONDS)
            time.sleep(0.4)
    return out


def compute(offline, now=None):
    raw = load_raw()
    if now is None:
        # waktu acuan = panggilan terakhir di log (reproducible), bukan jam laptop
        calls = raw.get("calls") or []
        now = max([c.get("server_time_unix") or c["ts_wall_unix"] for c in calls], default=int(time.time()))
    cal_path = _lib.p("data", "calibration.json")
    cal = json.load(open(cal_path)) if os.path.exists(cal_path) else None
    calib = cal["pairs"] if cal and cal.get("valid") else None
    bt_path = _lib.p("data", "backtest_full.json")
    bt = json.load(open(bt_path)) if os.path.exists(bt_path) else None
    candles = load_candles(offline, now) if calib else {}
    bt_orders = M.load_backtest_orders(_lib.p("data", "backtest_full_orders.csv"))
    return M.compute_all(raw, candles, calib, bt, now, bt_orders)


def canon(x):
    return json.loads(json.dumps(x, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--now", default=None, help="ISO UTC; default = panggilan terakhir di log")
    ap.add_argument("--verify", default=None, help="path dashboard.html untuk dicocokkan")
    a = ap.parse_args()
    D = canon(compute(a.offline, parse_iso(a.now) if a.now else None))
    if a.verify:
        H = R.extract_data(open(a.verify, encoding="utf-8").read())
        diffs = []

        def walk(x, y, path=""):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in set(x) | set(y):
                    walk(x.get(k), y.get(k), f"{path}.{k}")
            elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
                for i, (u, v) in enumerate(zip(x, y)):
                    walk(u, v, f"{path}[{i}]")
            elif isinstance(x, float) and isinstance(y, float):
                if abs(x - y) > 1e-9 * max(1.0, abs(x)):
                    diffs.append((path, x, y))
            elif x != y and path != ".generated_for_now":
                diffs.append((path, x, y))
        walk(D, H)
        if diffs:
            print(f"TIDAK COCOK: {len(diffs)} perbedaan")
            for d in diffs[:30]:
                print("  ", d)
            sys.exit(1)
        print("COCOK: semua angka di", a.verify, "identik dengan hasil hitung ulang dari log mentah")
        return
    json.dump(D, open(_lib.p("data", "dashboard_data.json"), "w"), indent=1, ensure_ascii=False)
    open(_lib.p("dashboard.html"), "w", encoding="utf-8").write(R.render(D))
    f = D["forward"]
    print("forward return:", f["total_return"], "maxDD:", f["max_drawdown"], "trades:", f["trades"])
    print("uptime:", D["uptime"]["uptime"], f"({D['uptime']['candles_on_time']}/{D['uptime']['candles_scheduled']})")
    if D["signal_match"]:
        print("kecocokan sinyal:", D["signal_match"]["matched"], "/", D["signal_match"]["compared"])
    print("-> data/dashboard_data.json, dashboard.html")


if __name__ == "__main__":
    main()
