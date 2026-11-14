"""Susun ZIP pengumpulan RISE dari repositori ini.

  python scripts/export_submission.py [--out ../UAS_Indodax_DryRun_25120200002.zip]

Isi: semua berkas yang terlacak git + folder .git utuh (bukti riwayat commit).
Berkas yang tidak terlacak (.env, .vercel/, data/candles/*.json) TIDAK ikut.
ZIP gagal dibuat bila berkas wajib hilang, ada perubahan yang belum di-commit,
atau ditemukan pola secret."""
import argparse
import os
import re
import subprocess
import sys
import zipfile

import _lib

REQUIRED = [
    "README.md", "STRATEGI.md", "REFLEKSI.md", "FREEZE.md", "FEES_SOURCES.md", ".env.example",
    "bot/strategy.py", "bot/engine.py", "bot/backtest_core.py", "api/tick.py", "api/dashboard.py",
    "scripts/hitung_ulang.py", "scripts/backtest.py", "dashboard.html",
    "data/calibration.json", "data/backtest_full.json", "data/backtest_full_orders.csv",
    "data/dashboard_data.json", "data/raw/calls.jsonl", "data/raw/signals.jsonl", "data/raw/orders.jsonl",
    "data/raw/equity_daily.jsonl", "data/raw/errors.jsonl", "data/raw/events.jsonl", "data/raw/snapshots.jsonl",
]
SECRET = re.compile(rb"vercel_blob_rw_[A-Za-z0-9]{6,}|CRON_SECRET=[A-Za-z0-9_\-]{8,}|Bearer [A-Za-z0-9_\-]{20,}")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=_lib.ROOT, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(_lib.ROOT), "UAS_Indodax_DryRun_25120200002.zip"))
    a = ap.parse_args()
    if git("status", "--porcelain", "--untracked-files=no").strip():
        sys.exit("Ada perubahan yang belum di-commit. Commit dulu agar ZIP sama dengan riwayat git.")
    tracked = [f for f in git("ls-files").splitlines() if f]
    missing = [f for f in REQUIRED if f not in tracked]
    if missing:
        sys.exit("Berkas wajib belum ada/terlacak: " + ", ".join(missing))
    leaks = [f for f in tracked if SECRET.search(open(_lib.p(f), "rb").read())]
    if leaks:
        sys.exit("Pola secret ditemukan di: " + ", ".join(leaks))
    head = git("log", "-1", "--format=%h %cI %s").strip()
    root = "indodaxtredraka"
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in tracked:
            z.write(_lib.p(f), f"{root}/{f}")
        for d, _, files in os.walk(_lib.p(".git")):
            for fn in files:
                full = os.path.join(d, fn)
                z.write(full, f"{root}/" + os.path.relpath(full, _lib.ROOT))
    with zipfile.ZipFile(a.out) as z:
        bad = z.testzip()
        names = z.namelist()
    if bad:
        sys.exit(f"ZIP rusak pada {bad}")
    assert not any(n.endswith("/.env") or "/.vercel/" in n for n in names)
    print(f"OK {a.out}")
    print(f"  HEAD {head}")
    print(f"  {len(tracked)} berkas terlacak + .git ({sum('/.git/' in n for n in names)} berkas)")
    print(f"  ukuran {os.path.getsize(a.out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
