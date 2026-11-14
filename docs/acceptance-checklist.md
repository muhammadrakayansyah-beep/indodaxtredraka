# Checklist penerimaan

Setiap butir dipetakan ke bukti yang bisa dicek di repositori ini. Status ✅ = terpenuhi dan terbukti; ⚠️ = terpenuhi sebagian, dengan penjelasan; ❌ = tidak terpenuhi.

| Butir | Status | Bukti |
|---|---|---|
| Tanpa endpoint order sungguhan, tanpa API key Indodax, tanpa leverage atau short | ✅ | `bot/indodax.py` hanya memanggil endpoint publik; `strategy.evaluate` long-only |
| Modal virtual awal Rp100.000.000 | ✅ | `bot/config.py` `INITIAL_CAPITAL_IDR`; event `state_init` di `data/raw/events.jsonl` |
| 3–10 pair IDR; seleksi likuiditas menghindari survivorship bias | ⚠️ | 4 pair. Uji point-in-time `data/universe_selection.json`: universe = peringkat 2–5; peringkat 1 USDT dikecualikan secara ex post (REFLEKSI 5.7) |
| Data historis ≥ 3 tahun, dapat ditelusuri ke Indodax | ✅ | `data/candles/*.json` (2022-08-01 s/d 2026-11-13, tanpa gap); hash cocok dengan `candles_meta` di `data/backtest_full.json` |
| Fungsi sinyal sama untuk backtest dan forward | ✅ | `bot/strategy.py::evaluate` dipanggil oleh `bot/engine.py` dan `bot/backtest_core.py`; `tests/test_blueprint.py::Parity`; kecocokan sinyal 24/24 |
| Hanya candle tertutup; data basi, bolong, atau tidak valid memblokir entry | ✅ | `bot/indodax.closed_only`, `bot/validation.py`; `tests/test_blueprint.py::Data` |
| Beli di ask, jual di bid, VWAP multi-level | ✅ | `bot/execution.py`; `tests/test_blueprint.py::Execution` |
| Fee taker all-in, minimum order, pembulatan kuantitas | ⚠️ | Diterapkan di kode. Fee 0,2222% belum diverifikasi ulang dari halaman resmi (`FEES_SOURCES.md`). Kenaikan harga tidak perlu dibulatkan karena harga fill berasal dari level order book |
| Batas posisi, ukuran posisi, daily loss limit, kill switch, retry terbatas, idempotency | ✅ | `docs/risk-policy.md`; `tests/test_core.py`, `tests/test_blueprint.py::Risk` |
| Storage persisten, endpoint tick terautentikasi | ✅ | Vercel Blob (`bot/storage.py`); `bot/auth.py` (401 tanpa secret) |
| Scheduler | ✅ | 8 cron Vercel harian (tiap 3 jam), cukup untuk timeframe 1D; drift median 0,32 menit |
| Setiap tick, order, ekuitas harian, error, dan snapshot dicatat | ✅ | `data/raw/*.jsonl` (42 panggilan, 168 snapshot, 6 ekuitas harian, 0 order, 0 error) |
| Metrik dihitung ulang dari log mentah dan cocok dengan kedua dashboard | ✅ | `scripts/hitung_ulang.py --verify`; `tests/test_blueprint.py::Reconciliation`; dashboard Vercel memakai `bot/metrics.py` yang sama |
| Tidak ada secret di riwayat git maupun ZIP | ✅ | Scan seluruh 22+ commit: hanya placeholder; `scripts/export_submission.py` menolak pola secret |
| Riwayat freeze autentik, tidak ditulis ulang | ⚠️ | Riwayat asli tanpa force-push. Namun **tidak ada commit freeze sebelum 4 Nov 12.00 WIB**; freeze de facto `218a6c1` (9 Nov 11.57 WIB). Lihat `FREEZE.md` |
| Forward test 10 hari | ❌ | Efektif 5 hari (bot mulai 9 Nov 04:01Z); uptime 6/10 |

## Rangkuman kekurangan yang tidak bisa diperbaiki setelah fakta

1. Commit freeze sebelum 4 Nov 2026 12.00 WIB tidak ada, dan tidak boleh dibuat mundur.
2. Candle 4–7 Nov tidak pernah diproses live.
3. Kalibrasi biaya dan uji universe dijalankan setelah forward test (14 Nov).

Ketiganya dilaporkan apa adanya di `REFLEKSI.md` dan `FREEZE.md`.
