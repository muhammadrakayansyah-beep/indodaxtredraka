"""Reset state bot ke modal awal Rp100 juta TEPAT saat forward test dimulai
(log persiapan tetap disimpan; metrik forward hanya memakai catatan di jendela forward).
  python scripts/reset_state.py --confirm"""
import argparse
import json
import time

import _lib
from bot import config as C
from bot import storage
from bot.engine import new_state
from bot.timeutil import iso

_lib.load_dotenv()
ap = argparse.ArgumentParser()
ap.add_argument("--confirm", action="store_true")
a = ap.parse_args()
if not a.confirm:
    raise SystemExit("Tambahkan --confirm. Ini menghapus posisi & kas simulasi saat ini.")
s = storage.from_env()
old = s.get("state")
s.set("state", json.dumps(new_state()))
s.append_many([("events", {"ts": iso(int(time.time())), "type": "forward_reset",
                           "capital": C.INITIAL_CAPITAL_IDR, "previous_state": json.loads(old) if old else None})])
print("state direset", iso(int(time.time())))
