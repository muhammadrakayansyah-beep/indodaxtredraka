"""Unduh log mentah dari Upstash Redis ke data/raw/<stream>.jsonl (+ CSV ringkas).
Butuh UPSTASH_REDIS_REST_URL/TOKEN di .env."""
import csv
import json

import _lib
from bot import storage

_lib.load_dotenv()


def main():
    store = storage.from_env()
    for s in storage.STREAMS:
        rows = store.read_stream(s)
        _lib.write_jsonl(_lib.p("data", "raw", f"{s}.jsonl"), rows)
        print(f"{s}: {len(rows)} baris")
        if s in ("orders", "calls", "equity_daily", "errors", "events", "signals") and rows:
            keys = sorted({k for r in rows for k in r})
            with open(_lib.p("data", "raw", f"{s}.csv"), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for r in rows:
                    w.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    st = store.get("state")
    open(_lib.p("data", "raw", "state_latest.json"), "w").write(st or "null")


if __name__ == "__main__":
    main()
