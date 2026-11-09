"""Catat perbaikan bug selama forward test (wajib menurut soal) ke log bot.
  python scripts/log_bugfix.py --commit <hash> --desc "..." """
import argparse
import time

import _lib
from bot import storage
from bot.timeutil import iso

_lib.load_dotenv()
ap = argparse.ArgumentParser()
ap.add_argument("--commit", required=True)
ap.add_argument("--desc", required=True)
a = ap.parse_args()
storage.from_env().append_many([("events", {"ts": iso(int(time.time())), "type": "bugfix_note",
                                            "commit": a.commit, "desc": a.desc,
                                            "rules_changed": False})])
print("tercatat")
