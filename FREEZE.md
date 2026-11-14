# Bukti freeze

> **Status: TIDAK ADA commit freeze yang sah.** Freeze resmi soal adalah Rabu 4 Nov 2026 12.00 WIB.
> Repositori ini baru dibuat 9 Nov 2026 (`386cfab`, 11.12 WIB) dan bot pertama kali berjalan
> 2026-11-09T04:01Z (11.01 WIB). Tidak ada commit yang tanggalnya dimundurkan.

## Kronologi aktual (dapat dicek di `git log` dan log bot)

| Waktu (WIB) | Kejadian |
|---|---|
| 9 Nov 11.01 | Bot di-deploy ke Vercel dan dipanggil pertama kali (uji koneksi 401/200 lolos) |
| 9 Nov 11.12 | Commit pertama repositori GitHub |
| 9 Nov 11.57 | Commit `218a6c1`: **freeze de facto**. Sejak commit ini, 8 file inti bot (`bot/strategy.py`, `config.py`, `validation.py`, `execution.py`, `backtest_core.py`, `engine.py`, `indodax.py`, `storage.py`) tidak berubah (hash sama dengan HEAD) |
| 9–14 Nov | Bot berjalan otomatis 8× sehari (Vercel Cron), state & log di Vercel Blob |
| 14 Nov 09.47 | Kalibrasi biaya (cutoff 2026-11-10T00:17:24Z) dan backtest 3 tahun |
| 14 Nov 09.55–10.50 | Beberapa deploy di dalam jendela forward: data backtest untuk dashboard, perapian nama berkas, logo dan nama di dashboard, sinkronisasi struktur repo. Kode sinyal, parameter, dan universe **tidak berubah**. Setiap deploy dicatat sebagai event `bugfix_note` di `data/raw/events.jsonl` |
| 14 Nov 12.00 | Akhir jendela forward (`FORWARD_END_UTC`) |

Akibat menurut rubrik: komponen kecocokan dapat dinilai 0 karena tidak ada commit freeze
sebelum forward test. Konsekuensi ini dilaporkan apa adanya di REFLEKSI.md.

Perubahan aturan terakhir sebelum bot berjalan (dicatat di STRATEGI.md, bagian "Catatan implementasi"):
volume nol diperiksa pada candle keputusan saja, harga referensi take-profit = Open candle setelah sinyal,
dan jendela indikator tetap 300 candle.

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
