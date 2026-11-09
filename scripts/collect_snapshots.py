"""Kumpulkan snapshot order book dari laptop (pelengkap snapshot yang disimpan bot).
  python scripts/collect_snapshots.py               # sekali
  python scripts/collect_snapshots.py --every 3600  # berulang tiap jam (biarkan berjalan)
Output: data/raw/snapshots_laptop.jsonl (format sama dengan stream `snapshots` bot)."""
import argparse
import time

import _lib
from bot import config as C
from bot import indodax as API
from bot.timeutil import iso

OUT = _lib.p("data", "raw", "snapshots_laptop.jsonl")


def once():
    now = API.server_time()
    for pair in C.UNIVERSE:
        b = API.depth(pair)
        _lib.append_jsonl(OUT, {"ts": iso(now), "ts_unix": now, "call_id": "laptop", "pair": pair,
                                "bids": b["bids"][:C.ORDERBOOK_LEVELS_TO_STORE],
                                "asks": b["asks"][:C.ORDERBOOK_LEVELS_TO_STORE]})
        time.sleep(0.4)
    print(iso(now), "snapshot tersimpan untuk", ", ".join(C.UNIVERSE))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=0)
    a = ap.parse_args()
    while True:
        try:
            once()
        except API.ApiError as e:
            print("gagal:", e)
        if not a.every:
            break
        time.sleep(a.every)
