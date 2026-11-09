"""Seleksi universe point-in-time: likuiditas diukur pada 30 hari SEBELUM awal backtest,
bukan hari ini. Kandidat = semua pair IDR di /api/pairs + daftar tambahan (mis. pair yang
sudah delisting) di data/extra_candidates.txt bila ada.

  python scripts/universe_selection.py --asof 2023-11-04 --top 4

Keterbatasan: /api/pairs hanya memuat pair yang MASIH listing. Pair yang delisting sebelum
hari ini tidak terlihat kecuali ditambahkan manual ke extra_candidates.txt -> catat di STRATEGI.md.
Output: data/universe_selection.json"""
import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone

import _lib
from bot import indodax as API
from bot.timeutil import iso


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=4)
    a = ap.parse_args()
    asof = int(datetime.strptime(a.asof, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    pairs = API.get_json("/api/pairs")
    cands = sorted({p["symbol"] for p in pairs if p.get("base_currency") == "idr"})
    extra = _lib.p("data", "extra_candidates.txt")
    if os.path.exists(extra):
        cands += [x.strip().upper() for x in open(extra) if x.strip() and x.strip().upper() not in cands]
    rows = []
    for i, sym in enumerate(cands):
        try:
            cs = API.history(sym, "1D", asof - a.days * 86400, asof - 1, retries=2)
        except API.ApiError as e:
            rows.append({"pair": sym, "error": str(e)})
            continue
        finally:
            time.sleep(0.4)
        cs = [c for c in cs if asof - a.days * 86400 <= c["Time"] < asof]
        vals = [c["Volume"] * c["Close"] for c in cs]
        rows.append({"pair": sym, "days_with_data": len(cs),
                     "median_daily_idr_value": statistics.median(vals) if vals else 0.0})
        if i % 25 == 0:
            print(f"{i}/{len(cands)}")
    eligible = [r for r in rows if r.get("days_with_data", 0) >= a.days - 1]
    eligible.sort(key=lambda r: -r["median_daily_idr_value"])
    out = {"asof": a.asof, "window_days": a.days, "measured_at": iso(int(time.time())),
           "rule": f"median nilai transaksi IDR harian (Volume*Close) {a.days} hari sebelum asof; "
                   f"wajib ada data >= {a.days - 1} hari; ambil top {a.top}",
           "selected": [r["pair"] for r in eligible[:a.top]], "ranking": eligible,
           "excluded_or_no_data": [r for r in rows if r not in eligible],
           "candidates_source": "https://indodax.com/api/pairs (+ data/extra_candidates.txt)",
           "limitation": "pair yang sudah delisting tidak muncul di /api/pairs"}
    json.dump(out, open(_lib.p("data", "universe_selection.json"), "w"), indent=2)
    print("Terpilih:", out["selected"])
    for r in eligible[: a.top + 6]:
        print(f"{r['pair']:<12} {r['median_daily_idr_value']:>20,.0f}")


if __name__ == "__main__":
    main()
