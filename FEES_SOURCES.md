# Sumber fee, minimum order, dan batas API

Isi/verifikasi tabel ini **sebelum freeze**, lalu salin angka final ke `bot/config.py`.

| Item | Nilai | Sumber (URL) | Tanggal akses | Status |
|---|---|---|---|---|
| `trade_fee_percent_taker` BTCIDR/ETHIDR/XRPIDR/DOGEIDR | 0,2% | https://indodax.com/api/pairs | 2026-11-09 (respons API dibaca di sesi pembuatan kode) | terverifikasi dari API |
| Fee taker all-in (termasuk pajak), halaman resmi | 0,2222% (menurut STRATEGI.md) | help.indodax.com, "Rincian Biaya Transaksi" (isi URL lengkap) | **belum diverifikasi**: halaman tidak bisa diakses dari lingkungan pembuatan kode | WAJIB dicek |
| Fee yang dipakai (yang lebih mahal) | 0,2222% → `TAKER_FEE = 0.002222` | — | — | ikut baris di atas |
| `trade_min_base_currency` | Rp10.000 | https://indodax.com/api/pairs | 2026-11-09 | terverifikasi dari API |
| Minimum order langsung mode Pro | Rp25.000 (menurut soal) | (isi URL halaman resmi) | (isi) | WAJIB dicek |
| Minimum yang dipakai | Rp25.000 → `MIN_ORDER_IDR` | — | — | — |
| Kenaikan kuantitas | 1e-08 (`quantity_increment`) | https://indodax.com/api/pairs | 2026-11-09 | terverifikasi dari API |
| Kenaikan harga | btc_idr: 1000 | https://indodax.com/api/price_increments | 2026-11-09 | terverifikasi dari API (tidak dipakai untuk market sweep; harga fill berasal dari level order book) |
| Batas API publik | 180 request/menit | soal UAS + github.com/btcid/indodax-official-api-docs | (isi) | cek |

Catatan perubahan tarif efektif 1 Oktober 2026 (menurut soal): pastikan angka halaman resmi adalah tarif yang berlaku pada tanggal pengujian.
