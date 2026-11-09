# Bukti freeze

> **Status per 9 Nov 2026: BELUM ADA commit freeze yang sah.** Freeze resmi soal adalah
> Rabu 4 Nov 2026 12.00 WIB dan sudah lewat. Repositori ini **tidak boleh** memakai commit yang
> tanggalnya dimundurkan (`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`), karena itu fabrikasi.
> Waktu push juga tercatat di GitHub, jadi pemundurannya bisa diaudit.

## Prosedur freeze (dijalankan sekali, pada waktu sebenarnya)

1. Pastikan bot sudah ter-deploy, `scripts/smoke_test.py` lolos (401 tanpa secret, 200 dengan secret),
   dan snapshot order book sudah ≥ 9 per pair.
2. `python scripts/export_logs.py` lalu `python scripts/calibrate_costs.py --cutoff <waktu freeze ISO UTC>` → `valid: true`.
3. `python scripts/fetch_history.py --start 2022-08-01` lalu `python scripts/backtest.py --from <≥3 th sebelum> --to <candle terakhir sebelum freeze>`.
4. Set `FORWARD_START_UTC` / `FORWARD_END_UTC` di `bot/config.py` (waktu nyata yang disetujui dosen).
5. `python scripts/freeze_manifest.py`
6. Commit dan push (jangan force-push sesudahnya):
   ```
   git add -A && git commit -m "FREEZE: aturan, parameter, universe, kalibrasi" && git tag freeze && git push origin main --tags
   ```
7. `python scripts/reset_state.py --confirm` tepat saat forward test dimulai.
8. Catat di bawah:

| Item | Nilai |
|---|---|
| Hash commit freeze | (isi dari `git rev-parse freeze`) |
| Waktu commit (UTC/WIB) | (isi dari `git show -s --format=%cI freeze`) |
| Mulai forward (UTC) | |
| Akhir forward (UTC) | |
| Persetujuan dosen untuk recovery/late run | (isi: tanggal, kanal, kutipan) |

Perbaikan bug selama forward test yang tidak mengubah aturan: commit biasa, lalu
`python scripts/log_bugfix.py --commit <hash> --desc "..."`. File yang tercantum di
`data/freeze_manifest.json` (kecuali `bot/engine.py` untuk bugfix non-aturan) tidak boleh berubah.
