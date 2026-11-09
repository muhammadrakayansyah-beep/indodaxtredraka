"""Kill switch tanpa redeploy: set key Redis indodax-dryrun:kill_switch.
  python scripts/kill_switch.py on|off|status --reason "..."
Perubahan juga tercatat oleh bot pada panggilan berikutnya (event kill_switch_on/off)."""
import argparse
import time

import _lib
from bot import storage
from bot.timeutil import iso

_lib.load_dotenv()

ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["on", "off", "status"])
ap.add_argument("--reason", default="")
a = ap.parse_args()
s = storage.from_env()
if a.cmd == "status":
    print("kill_switch =", s.get("kill_switch"))
else:
    s.set("kill_switch", "1" if a.cmd == "on" else "0")
    s.append_many([("events", {"ts": iso(int(time.time())), "type": f"kill_switch_manual_{a.cmd}",
                               "reason": a.reason, "source": "scripts/kill_switch.py"})])
    print("kill_switch ->", a.cmd)
