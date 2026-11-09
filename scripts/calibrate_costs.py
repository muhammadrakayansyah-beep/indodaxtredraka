"""Kalibrasi spread & slippage backtest dari snapshot order book MENTAH yang diambil
sebelum --cutoff (waktu freeze). Gagal (valid=false) bila snapshot < MIN_SNAPSHOTS_PER_PAIR.
  python scripts/calibrate_costs.py --cutoff 2026-11-04T05:00:00Z
Output: data/calibration.json"""
import argparse
import glob
import json

import _lib
from bot import config as C
from bot import metrics as M
from bot.timeutil import iso, parse_iso


def load_snapshots():
    rows, files = [], []
    for f in sorted(glob.glob(_lib.p("data", "raw", "snapshots*.jsonl"))):
        r = _lib.read_jsonl(f)
        rows += r
        files.append({"file": f.replace(_lib.ROOT + "/", ""), "rows": len(r), "sha256": _lib.sha256_file(f)})
    rows.sort(key=lambda s: s["ts_unix"])
    return rows, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", required=True, help="ISO UTC, mis. waktu freeze")
    a = ap.parse_args()
    cut = parse_iso(a.cutoff)
    snaps, files = load_snapshots()
    stats = M.snapshot_costs(snaps, cut)
    problems = []
    for p in C.UNIVERSE:
        s = stats.get(p)
        if not s or s["n"] < C.MIN_SNAPSHOTS_PER_PAIR:
            problems.append(f"{p}: snapshot {s['n'] if s else 0} < {C.MIN_SNAPSHOTS_PER_PAIR}")
        elif s["buy_slip"] is None or s["sell_slip"] is None:
            problems.append(f"{p}: slippage tidak terukur (buku tidak cukup dalam untuk order referensi)")
    used = [s for s in snaps if s["ts_unix"] < cut]
    out = {"valid": not problems, "problems": problems, "cutoff": a.cutoff,
           "method": "median per pair; half_spread=(ask-bid)/mid/2; slip=VWAP order Rp10jt vs best price",
           "snapshot_time_range": [iso(used[0]["ts_unix"]), iso(used[-1]["ts_unix"])] if used else None,
           "source_files": files, "pairs": stats}
    json.dump(out, open(_lib.p("data", "calibration.json"), "w"), indent=2)
    print(json.dumps({k: out[k] for k in ("valid", "problems", "snapshot_time_range")}, indent=2))
    for p, s in stats.items():
        print(p, s)


if __name__ == "__main__":
    main()
