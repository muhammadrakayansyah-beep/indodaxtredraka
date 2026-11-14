# Change log

Sumber: `git log` repositori ini, `data/raw/events.jsonl` (event `bugfix_note`), dan `STRATEGI.md`.

## Dari strategi UTS ke bot dry run (sebelum bot berjalan, 9 Nov 2026)

| Perubahan | Alasan |
|---|---|
| Saham harian → pasangan kripto IDR Indodax, timeframe tetap 1D | Ketentuan UAS |
| Universe: BTCIDR, ETHIDR, XRPIDR, DOGEIDR | Lihat `data/universe_selection.json` untuk uji point-in-time |
| Maksimum 4 posisi (satu per pair), maksimum 10% ekuitas per posisi | Risk management wajib |
| Eksekusi live: beli menyapu ask, jual menyapu bid; fee taker 0,2222%; minimum Rp25.000 | Ketentuan eksekusi dry run |
| Daily loss limit 2% per hari WIB, kill switch tanpa redeploy | Risk management wajib |
| Harga referensi take-profit = Open candle setelah sinyal | UTS mengeksekusi di open bar berikutnya; nilai ini berasal dari candle sehingga backtest dan live identik |
| Indikator selalu dari tepat 300 candle tertutup terakhir | RSI Wilder bergantung pada titik awal; jendela tetap membuat nilainya identik di backtest dan live |
| Volume nol diperiksa pada candle keputusan saja | Data Indodax asli memuat volume 0 pada 2024-09-12 (semua pair) dan 2024-09-13 (ETH, XRP, DOGE). Jika diperiksa di seluruh jendela, satu hari itu memblokir sinyal sekitar 300 hari |

## Riwayat commit

| Waktu (WIB) | Commit | Isi | Mengubah aturan? |
|---|---|---|---|
| 9 Nov 11.12 | `386cfab` | Initial commit | — |
| 9 Nov 11.52 | `f226e3b` | Upload source code bot | — |
| 9 Nov 11.57 | `218a6c1` | Upload source code (lengkap) | **Freeze de facto**: 8 file inti bot (`strategy`, `config`, `validation`, `execution`, `backtest_core`, `engine`, `indodax`, `storage`) identik dengan HEAD |
| 14 Nov 09.54–10.34 | `6457e9b` … `2d4ba04` | Upload data backtest, pindah ke `data/`, hapus `__pycache__`, perbaikan nama CSV | Tidak |
| 14 Nov 10.45 | `409a9ab` | Logo dan nama/NIM di dashboard (`bot/report.py`, `bot/assets/logo.png`) | Tidak (tampilan) |
| 14 Nov 11.28 | `c50bf8f` | Sinkronisasi struktur repo (`.vercelignore`, `.env.example`, README, FREEZE) | Tidak |
| 14 Nov 12.11 | `d8c1e9c` | Data final forward: log mentah, `dashboard_data.json`, `dashboard.html` | Tidak |
| 14 Nov 18.38–18.44 | `c0c5152`, `5efa9d9`, `3e19649` | Panel order simulasi, banner 0 order, perbaikan waktu acuan `hitung_ulang` | Tidak (tampilan/skrip analisis) |

## Deploy di dalam jendela forward

Ada 9 event `bugfix_note` di `data/raw/events.jsonl`, semuanya pada 14 Nov 09.48–11.29 WIB. Seluruhnya berupa penambahan data untuk dashboard, perapian nama berkas, tampilan dashboard, atau dokumentasi. Fungsi sinyal, parameter, universe, dan model eksekusi bot **tidak berubah**: hash 8 file inti bot sama dengan commit `218a6c1`.

## Perbaikan skrip setelah forward test

- `scripts/universe_selection.py`: memanggil `API.history` dengan argumen yang tidak ada (`retries`), dan mencoba ulang respons kosong 3 kali untuk setiap pair yang belum listing. Diperbaiki menjadi satu percobaan per pair; respons kosong dicatat "tidak ada data". Skrip ini baru dijalankan pertama kali pada 14 Nov.
- `scripts/hitung_ulang.py`: waktu acuan sebelumnya = panggilan bot terakhir, sehingga dashboard offline yang dibuat setelah 12.00 WIB masih menyatakan "forward belum selesai". Waktu acuan kini disimpan dan dipakai ulang oleh `--verify`.
