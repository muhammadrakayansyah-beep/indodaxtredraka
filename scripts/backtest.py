"""Backtest penuh (>= 3 tahun) dengan candle Indodax asli + biaya hasil kalibrasi.
  python scripts/backtest.py --from 2023-11-04 --to 2026-11-03
Butuh data/candles/<PAIR>_1D.json (fetch_history.py) dan data/calibration.json valid.
Output: data/backtest_full.json, data/backtest_full_orders.csv"""
import argparse
import csv
import json
import sys
from datetime import datetime, timezone

import _lib
from bot import backtest_core as BT
from bot import config as C
from bot import metrics as M
from bot.timeutil import iso


def load_candles():
    out, meta = {}, {}
    for p in C.UNIVERSE:
        path = _lib.p("data", "candles", f"{p}_{C.TIMEFRAME}.json")
        d = json.load(open(path))
        out[p] = d["candles"]
        meta[p] = {"file": path.replace(_lib.ROOT + "/", ""), "sha256": _lib.sha256_file(path),
                   "fetched_at": d["fetched_at"], "first": d["first"], "last": d["last"], "gaps": d["gaps"]}
    return out, meta


def ts(s):
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", required=True)
    ap.add_argument("--to", required=True)
    a = ap.parse_args()
    cal = json.load(open(_lib.p("data", "calibration.json")))
    if not cal.get("valid"):
        sys.exit("Kalibrasi tidak valid -> backtest TIDAK dijalankan: " + "; ".join(cal.get("problems", [])))
    calib = cal["pairs"]
    candles, meta = load_candles()
    f, t = ts(a.frm), ts(a.to)
    if (t - f) < 3 * 365 * 86400:
        sys.exit("Periode backtest kurang dari 3 tahun")
    for p in C.UNIVERSE:
        first = candles[p][0]["Time"]
        if f - first < (C.INDICATOR_WINDOW - 1) * C.TF_SECONDS:
            print(f"PERINGATAN {p}: warm-up indikator kurang; sinyal awal akan INVALID", file=sys.stderr)
    res = BT.run(candles, calib, f, t)
    summ = M.summarize_backtest(res, candles, calib, f, t)
    curve = summ.pop("equity_curve")
    summ["equity_curve_weekly"] = curve[::7] + ([curve[-1]] if curve and (len(curve) - 1) % 7 else [])
    summ["invalid_signal_count"] = sum(1 for s in res["signals"] if s.get("action") == "INVALID")
    summ["blocked_entries"] = [s for s in res["signals"] if "exec_blocked" in s]
    summ["calibration_cutoff"] = cal["cutoff"]
    summ["calibration_sha256"] = _lib.sha256_file(_lib.p("data", "calibration.json"))
    summ["candles_meta"] = meta
    summ["fee_rate"] = C.TAKER_FEE
    summ["strategy_version"] = C.STRATEGY_VERSION
    json.dump(summ, open(_lib.p("data", "backtest_full.json"), "w"), indent=1, default=str)
    with open(_lib.p("data", "backtest_full_orders.csv"), "w", newline="") as fh:
        keys = sorted({k for o in res["orders"] for k in o})
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for o in res["orders"]:
            w.writerow({**o, "time": iso(o["time"])})
    for k in ("eval_from", "eval_to", "total_return", "cagr", "max_drawdown", "trades", "win_rate",
              "profit_factor", "cost_share_of_gross", "benchmark_btc_buy_hold"):
        print(f"{k:>22}: {summ.get(k)}")


if __name__ == "__main__":
    main()
