"""Tarik candle historis Indodax MUNDUR (history_v2 hanya mengembalikan bar terakhir
sebelum `to`). Sekuensial, maks ~2,5 request/detik. Jalankan di laptop, bukan di Vercel.

  python scripts/fetch_history.py --start 2022-08-01 [--pairs BTCIDR,ETHIDR] [--tf 1D]
"""
import argparse
import json
import time
from datetime import datetime, timezone

import _lib
from bot import config as C
from bot import indodax as API
from bot.timeutil import iso

SLEEP_S = 0.4  # <= 3 request/detik


def fetch_back(pair, tf, tf_s, start_ts, end_ts, log):
    by_time, to, n = {}, end_ts, 0
    while True:
        batch = API.history(pair, tf, start_ts, to)
        n += 1
        time.sleep(SLEEP_S)
        new = [c for c in batch if c["Time"] not in by_time]
        for c in batch:
            by_time[c["Time"]] = c
        earliest = min(c["Time"] for c in batch) if batch else None
        log(f"{pair} req#{n} to={iso(to)} dapat={len(batch)} baru={len(new)} "
            f"terawal={iso(earliest) if earliest else '-'}")
        if not batch or not new or earliest <= start_ts:
            break
        to = earliest - 1
    rows = sorted((c for c in by_time.values() if start_ts <= c["Time"] <= end_ts), key=lambda c: c["Time"])
    return rows, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC), termasuk warm-up indikator")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (UTC), default sekarang")
    ap.add_argument("--pairs", default=",".join(C.UNIVERSE))
    ap.add_argument("--tf", default=C.TIMEFRAME)
    a = ap.parse_args()
    tf_s = {"1": 60, "15": 900, "30": 1800, "60": 3600, "240": 14400, "1D": 86400}[a.tf]
    start = int(datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    now = API.server_time()
    end = int(datetime.strptime(a.end, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) if a.end else now
    for pair in a.pairs.split(","):
        rows, n = fetch_back(pair, a.tf, tf_s, start, end, print)
        closed = API.closed_only(rows, now, tf_s)
        gaps = [(x["Time"], y["Time"]) for x, y in zip(closed, closed[1:]) if y["Time"] - x["Time"] != tf_s]
        out = {"pair": pair, "tf": a.tf, "fetched_at": iso(now), "server_time": now, "requests": n,
               "source": "https://indodax.com/tradingview/history_v2", "first": iso(closed[0]["Time"]) if closed else None,
               "last": iso(closed[-1]["Time"]) if closed else None, "n": len(closed),
               "gaps": [[iso(x), iso(y)] for x, y in gaps], "candles": closed}
        path = _lib.p("data", "candles", f"{pair}_{a.tf}.json")
        json.dump(out, open(path, "w"))
        print(f"OK {pair}: {len(closed)} candle tertutup {out['first']} .. {out['last']}, gap={len(gaps)} -> {path}")


if __name__ == "__main__":
    main()
