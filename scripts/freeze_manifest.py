"""Tulis data/freeze_manifest.json: hash berkas aturan/parameter/universe/kalibrasi.
Jalankan tepat sebelum commit freeze, lalu commit + push + tag."""
import json
import subprocess
import time

import _lib
from bot import config as C
from bot.timeutil import iso

FILES = ["bot/config.py", "bot/strategy.py", "bot/validation.py", "bot/execution.py", "bot/backtest_core.py",
         "bot/engine.py", "data/calibration.json", "data/backtest_full.json", "STRATEGI.md"]
out = {"created_at_utc": iso(int(time.time())), "strategy_version": C.STRATEGY_VERSION,
       "universe": C.UNIVERSE, "forward_start_utc": C.FORWARD_START_UTC, "forward_end_utc": C.FORWARD_END_UTC,
       "taker_fee": C.TAKER_FEE, "min_order_idr": C.MIN_ORDER_IDR,
       "files": {}}
for f in FILES:
    try:
        out["files"][f] = _lib.sha256_file(_lib.p(f))
    except FileNotFoundError:
        out["files"][f] = None
try:
    out["parent_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_lib.ROOT, text=True).strip()
except Exception:
    out["parent_commit"] = None
json.dump(out, open(_lib.p("data", "freeze_manifest.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
missing = [f for f, h in out["files"].items() if h is None]
if missing:
    print("PERINGATAN: berkas belum ada:", missing)
