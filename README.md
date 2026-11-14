# Bot Dry Run Indodax di Vercel (UAS Algoritma Trading)

Bot trading **dry run** (order simulasi, tanpa uang sungguhan, tanpa API key). Bot membaca candle dan order book **asli** dari API publik Indodax, mengeksekusi simulasi di bid/ask dengan menyapu level order book, lalu menyimpan setiap keputusan ke Vercel Blob. Bot berjalan sebagai endpoint Vercel `/api/tick`.

- Strategi: lihat [STRATEGI.md](STRATEGI.md) (Mean Reversion RSI(4) < 10 + filter SMA50/200, harian, long-only).
- Status freeze: lihat [FREEZE.md](FREEZE.md). **Belum ada commit freeze yang sah.**
- Sumber fee dan minimum order: [FEES_SOURCES.md](FEES_SOURCES.md).
- Refleksi: [REFLEKSI.md](REFLEKSI.md) (final; angka dari `data/dashboard_data.json`).
- Model eksekusi: [docs/execution-model.md](docs/execution-model.md) · Kebijakan risiko: [docs/risk-policy.md](docs/risk-policy.md) · Change log: [docs/change-log.md](docs/change-log.md)

Hanya memakai **standard library Python 3.9+**. Tidak ada dependensi pihak ketiga.

## Deployment aktif

- Dashboard: https://indodax-dryrun.vercel.app (project Vercel `indodax-dryrun`, team `rakk`)
- Storage: Vercel Blob `indodax-dryrun-store` (sin1); env `BLOB_READ_WRITE_TOKEN` terpasang otomatis
- Repositori: https://github.com/muhammadrakayansyah-beep/indodaxtredraka. Project Vercel terhubung ke repo ini: setiap push ke `main` otomatis di-deploy ke production.
- Penjadwal: 8 Vercel Cron harian (00:17, 03:17, …, 21:17 UTC = setiap 3 jam), didefinisikan di `vercel.json`. Batas Hobby "sekali sehari" berlaku per job, jadi bot tetap dipanggil 8× sehari tanpa penjadwal luar.
- Setiap deploy di dalam jendela forward dicatat di log bot sebagai event `bugfix_note` (`scripts/log_bugfix.py`).
- Bot pertama kali dipanggil 2026-11-09T04:01Z. Jendela di `bot/config.py` masih jadwal resmi (4–14 Nov), sehingga candle 5–8 Nov tercatat **tidak diproses** pada uptime. Itu fakta, bukan bug.
- Kill switch tanpa redeploy: isi `BLOB_READ_WRITE_TOKEN` di `.env` lalu jalankan `python scripts/kill_switch.py on`, atau unggah `kv/kill_switch.json` berisi `1` lewat Vercel → Storage.

## Struktur

```
api/tick.py           endpoint bot (dilindungi CRON_SECRET)
api/dashboard.py      dashboard publik read-only; dipasang juga di "/"
bot/strategy.py       FUNGSI SINYAL TUNGGAL: dipakai bot dan backtest
bot/config.py         semua parameter, universe, fee, jendela forward (dibekukan)
bot/engine.py         satu panggilan: lock, idempotency, kill switch, daily loss, eksekusi, log
bot/execution.py      sapu order book (beli di ask, jual di bid), pembulatan qty
bot/validation.py     validasi candle & order book (dipakai bot dan backtest)
bot/backtest_core.py  mesin backtest
bot/metrics.py        semua angka dashboard (dipakai hitung_ulang dan dashboard Vercel)
bot/report.py         render HTML mandiri (offline, tanpa library luar)
bot/indodax.py        klien API publik: timeout + retry terbatas
bot/storage.py        Vercel Blob / Upstash Redis REST (+ file lokal untuk tes)
scripts/              fetch_history, collect_snapshots, calibrate_costs, universe_selection,
                      backtest, export_logs, hitung_ulang, kill_switch, reset_state,
                      log_bugfix, freeze_manifest, smoke_test, export_submission
docs/                 execution-model.md, risk-policy.md, change-log.md
tests/test_core.py    unit test (sinyal, candle tertutup, sweep, auth, idempotency, kill switch, retry)
vercel.json           konfigurasi fungsi + 8 cron harian
.vercelignore         berkas yang tidak ikut deploy
bot/assets/logo.png   logo dashboard (disematkan sebagai data URI)
data/                 calibration.json, backtest_full.json, backtest_full_orders.csv,
                      raw/ (log mentah forward), dashboard_data.json
dashboard.html        dashboard offline mandiri (hasil hitung_ulang.py)
```

## Alur data dan log

Setiap panggilan `/api/tick`:
1. mengambil lock storage (Blob: `lock.json` dibuat tanpa overwrite; Redis: `SET NX EX 240`); panggilan paralel dicatat sebagai `skipped_locked`;
2. membaca `server_time` Indodax, lalu membuang candle dengan `Time + 86400 > server_time`;
3. membaca kill switch (Blob `kv/kill_switch.json` / key Redis `indodax-dryrun:kill_switch`, atau env `KILL_SWITCH`);
4. mengambil order book semua pair dan menyimpan **snapshot mentah** (50 level per sisi);
5. menandai ekuitas pada **best bid**. Panggilan pertama setelah 00:00 WIB menulis `equity_daily` dan mereset batas daily loss;
6. untuk tiap pair: memproses candle tertutup terbaru **hanya sekali** (`last_processed`), memvalidasi data, memanggil `strategy.evaluate`, lalu mengeksekusi simulasi;
7. menulis log (Blob: satu berkas `logs/<UTC>-<id>.json` per panggilan) dengan stream `calls`, `signals`, `orders`, `equity_daily`, `errors`, `events`, `snapshots`.

Setiap order mencatat waktu, pair, sisi, qty, best bid/ask, mid, VWAP fill, fee, harga sinyal, selisih terhadap sinyal, jumlah level yang tersapu, dan biaya spread+slippage.

## Menjalankan lokal

```bash
python -m unittest discover -s tests -v
```

```bash
LOCAL_STORE=/tmp/bot.json python -c "from bot import engine, storage; print(engine.run_tick(storage.from_env(), 'local'))"
```

## Deploy ke Vercel

1. Push repositori ke GitHub (**publik**), lalu import di Vercel (Framework: Other). Setiap push ke `main` otomatis di-deploy.
2. Vercel → Storage → buat **Blob** store → hubungkan ke project (`BLOB_READ_WRITE_TOKEN` otomatis). Alternatif: Upstash Redis (`UPSTASH_REDIS_REST_URL`/`TOKEN` atau `KV_REST_API_URL`/`TOKEN`).
3. Vercel → Settings → Environment Variables: `CRON_SECRET` (≥16 karakter acak). Vercel Cron otomatis mengirim `Authorization: Bearer <CRON_SECRET>`.
4. Deploy. `vercel.json` memasang 8 cron harian (setiap 3 jam, menit ke-17).
5. Uji koneksi dari fungsi Vercel (bukti wajib masa persiapan). Isi `.env` lokal (lihat `.env.example`), lalu:
   ```bash
   python scripts/smoke_test.py
   ```
   Hasilnya: tanpa secret 401, dengan secret 200 dan `server_time` Indodax terbaca. Bukti tersimpan di `data/smoke_test.jsonl`.
6. Dashboard: `https://xxx.vercel.app/` (atau `/api/dashboard`).

## Backtest (di laptop, bukan di Vercel)

```bash
python scripts/fetch_history.py --start 2022-08-01
```

```bash
python scripts/universe_selection.py --asof 2023-11-04 --top 4
```

```bash
python scripts/export_logs.py
```

```bash
python scripts/calibrate_costs.py --cutoff 2026-11-04T05:00:00Z
```

```bash
python scripts/backtest.py --from 2023-11-04 --to 2026-11-03
```

- `fetch_history.py` menarik data **mundur** (geser `to` ke bar paling awal), sekuensial, jeda 0,4 detik. Hasil uji 9 Nov 2026: tf=1D mengembalikan seluruh rentang dalam 1 request; tf=60 butuh beberapa request (649 bar per request).
- `calibrate_costs.py` hanya memakai snapshot **sebelum** cutoff dan menolak (`valid:false`) bila snapshot < 9 per pair. `backtest.py` menolak berjalan dengan kalibrasi tidak valid. Tidak ada biaya default atau buatan.
- `universe_selection.py` mengukur likuiditas 30 hari **sebelum awal backtest**. Keterbatasannya: `/api/pairs` tidak memuat pair yang sudah delisting. Tambahkan pair tersebut ke `data/extra_candidates.txt` bila diketahui.

## Selama dan setelah forward test

```bash
python scripts/kill_switch.py on --reason "..."
```

```bash
python scripts/export_logs.py
```

```bash
python scripts/hitung_ulang.py
```

```bash
python scripts/hitung_ulang.py --verify dashboard.html
```

`hitung_ulang.py` menghasilkan `data/dashboard_data.json` dan `dashboard.html` (offline, mandiri) dari log mentah di `data/raw/`, ditambah candle Indodax untuk replay backtest pada jendela yang sama. `--verify` memastikan setiap angka di HTML identik dengan hasil hitung ulang.

Paket pengumpulan RISE (berkas terlacak + folder `.git`, dengan cek berkas wajib dan secret):

```bash
python scripts/export_submission.py
``` Dashboard Vercel memakai `bot/metrics.py` dan `bot/report.py` yang sama.

## Keamanan

- `.env` ada di `.gitignore`; hanya `.env.example` (kosong) yang di-commit.
- `/api/tick` menolak semua permintaan tanpa `Authorization: Bearer <CRON_SECRET>` (perbandingan constant-time). Bila `CRON_SECRET` kosong, endpoint gagal tertutup (fail closed).
- Tidak memakai API key Indodax; hanya endpoint publik.
- Dashboard bersifat read-only dan tidak menampilkan secret.
