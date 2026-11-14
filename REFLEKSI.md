# Refleksi forward test vs backtest

Penyusun: Muhammad Rakah Yansyah (NIM 25120200002). Strategi `mr-rsi4-sma200-v1`, universe BTCIDR, ETHIDR, XRPIDR, DOGEIDR, timeframe 1D.

Semua angka di bawah berasal dari `data/dashboard_data.json`, hasil `scripts/hitung_ulang.py` atas log mentah `data/raw/`. Angka-angka itu bisa dibuat ulang dengan `python scripts/hitung_ulang.py --verify dashboard.html`. Tidak ada angka yang diketik dari ingatan.

## 0. Ringkasan

| Metrik | Forward (live) | Backtest pada candle yang sama | Gap |
|---|---|---|---|
| Return total | 0,00% | 0,00% | 0,00 pp |
| Max drawdown | 0,00% | 0,00% | 0,00 pp |
| Trade | 0 | 0 | 0 |
| Kecocokan sinyal per candle | 24/24 (100%) | | |
| Buy & hold BTC/IDR | −9,15% (ask 9 Nov 04:01Z → bid 14 Nov 03:17Z, termasuk fee) | −10,99% (Open 3 Nov → Close 13 Nov) | periode berbeda, tidak dibandingkan langsung |

Backtest penuh (4 Nov 2023 – 3 Nov 2026): return 5,10%, CAGR 1,67%, max drawdown −1,00%, 12 trade tertutup (semuanya untung, plus 1 posisi ETH masih terbuka). Buy & hold BTC pada periode yang sama: +157,38%.

## 1. Paritas sinyal

Bot live dan backtest memanggil fungsi yang sama, `bot/strategy.py::evaluate`, dengan jendela tetap 300 candle tertutup. Pada 6 candle yang diproses live (8–13 Nov) × 4 pair, aksi live dan replay backtest **identik 24/24**. Semua aksinya HOLD.

**Kenapa 0 trade.** Syarat entry adalah RSI(4) < 10 **dan** close > SMA200 **dan** SMA50 > SMA200. Selama forward, pasar turun:

- **XRP** memenuhi syarat RSI pada 9, 10, 11, 12, dan 13 Nov (RSI 9,9 / 6,8 / 9,1 / 8,6 / 5,7). Namun close (18.468–19.844) selalu di bawah SMA200 (22.438–22.550), jadi filter tren memblokirnya.
- **BTC dan ETH** tidak pernah turun ke RSI < 10 (terendah 11,2 dan 10,5 pada 13 Nov). Selain itu, close ETH sudah di bawah SMA200 sejak 10 Nov, dan close BTC sejak 13 Nov.
- **DOGE** gagal di ketiga syarat; SMA50 < SMA200 sepanjang periode.

0 trade ini konsisten dengan frekuensi historis strategi: hanya 13 entry dalam 3 tahun backtest, atau sekitar 1 entry per 84 hari.

## 2. Selisih harga fill

Tidak ada order forward, jadi tidak ada selisih fill per trade yang bisa diurai. Sebagai gantinya, dashboard menampilkan **uji eksekusi** (bukan trade) dengan order Rp9,98 juta di snapshot order book terakhir (14 Nov 03:17Z). Biaya bolak-balik termasuk fee:

| Pair | Slip beli | Slip jual | Biaya bolak-balik |
|---|---|---|---|
| BTC | 0,0000% | 0,0068% | 0,451% |
| ETH | 0,0000% | 0,0491% | 0,496% |
| XRP | 0,0000% | 0,3293% | 0,778% |
| DOGE | 0,0000% | 0,1495% | 0,680% |

Fee saja sudah 0,444% (2 × 0,2222%). Untuk target take-profit 3%, biaya nyata sekali trade menggerus 15–26% dari target. Di backtest, porsi biaya terhadap laba kotor adalah 9,60%. Angka itu lebih kecil karena backtest memakai median slippage, yang bernilai 0 untuk sebagian besar pair (lihat bagian 3).

Keterlambatan eksekusi live: candle 9–13 Nov diproses **17,4 menit** setelah close. Candle 8 Nov diproses 241,9 menit setelah close karena bot baru dihidupkan 9 Nov 04:01Z. Backtest mengasumsikan eksekusi di Open, tepat saat candle berikutnya dibuka.

## 3. Spread dan slippage: backtest vs seluruh snapshot

Backtest memakai median dari 9 snapshot per pair (9 Nov 04:01Z – 10 Nov 00:17Z, cutoff ditetapkan dengan aturan "tepat setelah snapshot ke-9"). Seluruh snapshot berjumlah 42 per pair.

| Pair | Half-spread backtest (n=9) | Half-spread semua snapshot (n=42) | Rasio |
|---|---|---|---|
| BTC | 0,0016% | 0,0033% | 2,0× |
| ETH | 0,0144% | 0,0295% | 2,0× |
| XRP | 0,0381% | 0,0338% | 0,9× |
| DOGE | 0,0402% | 0,0790% | 2,0× |

Kesimpulan:

1. Untuk 3 dari 4 pair, spread yang dipakai backtest sekitar **separuh** kondisi seluruh periode. Backtest jadi sedikit terlalu optimistis.
2. Dampak absolutnya kecil dibanding fee. Kenaikan half-spread 0,002–0,04% per sisi jauh di bawah fee 0,2222% per sisi.
3. Median slippage order Rp10 juta bernilai 0 karena level terbaik biasanya cukup tebal, tetapi ekornya nyata. Di snapshot kalibrasi, slip beli mencapai 0,081% (BTC) dan 0,219% (XRP). Median tidak menangkap risiko ini.
4. Kalibrasi hanya mencakup sekitar 20 jam pertama. Variasi spread antarjam dan antarhari belum terwakili.

## 4. Keterlambatan scheduler dan uptime

| Metrik | Nilai |
|---|---|
| Panggilan terlaksana | 42 (40 Vercel Cron + 2 uji koneksi), semua `ok`, 0 error API |
| Keterlambatan cron dari menit ke-17 | median 0,32 menit, maks 0,83 menit (n = 40) |
| Durasi per panggilan | median 10,4 detik, maks 11,9 detik (batas Hobby 300 detik) |
| **Uptime candle** | **6/10 = 60%** |

Uptime 60% **bukan** gangguan Indodax atau Vercel. Candle 4–7 Nov tidak diproses karena bot baru dideploy 9 Nov 2026 04:01Z, lima hari setelah jadwal resmi. Sejak bot berjalan, 6 dari 6 candle terproses tepat waktu (100%). Satu candle bisa dicoba hingga 8 kali per hari (cron tiap 3 jam), sehingga keterlambatan cron Vercel Hobby (±59 menit) tidak mengancam batas "sebelum candle berikutnya ditutup".

## 5. Keterbatasan yang diakui

1. **Tidak ada commit freeze sebelum 4 Nov 2026 12.00 WIB.** Repositori dibuat 9 Nov. Aturan, parameter, dan kode eksekusi identik sejak commit `218a6c1` (9 Nov 11.57 WIB); ini *freeze de facto* yang terlambat 5 hari. Commit itu juga 56 menit setelah panggilan bot pertama, tetapi candle pertama yang diproses (8 Nov) sudah memakai kode yang sama persis (hash `bot/strategy.py` identik). Menurut rubrik, komponen kecocokan dapat dinilai 0 karena hal ini.
2. **Jendela forward efektif hanya 5 hari** (9–14 Nov), bukan 10 hari.
3. **Deploy di dalam jendela forward:** 9 event `bugfix_note` pada 14 Nov 09.48–11.29 WIB, semuanya untuk data dashboard, nama berkas, tampilan, atau dokumentasi. Fungsi sinyal dan parameter tidak berubah (lihat `docs/change-log.md`).
4. **Kalibrasi biaya ditentukan ex post** (14 Nov), dengan aturan cutoff yang ditetapkan sebelum melihat hasil backtest. Snapshot berasal dari dalam periode forward resmi.
5. **Sampel backtest kecil:** 12 trade dalam 3 tahun. Win rate 100% tidak bermakna secara statistik, dan strategi tidak punya stop loss sehingga satu trade buruk bisa menghapus banyak trade untung. Max drawdown −1% kecil karena eksposur rendah (10% per posisi, jarang memegang posisi), bukan karena strategi ini aman.
6. **Fee all-in 0,2222%** belum diverifikasi ulang dari halaman resmi Indodax (lihat `FEES_SOURCES.md`). `/api/pairs` menunjukkan 0,2%.
7. **Universe:** lihat `data/universe_selection.json` untuk hasil uji point-in-time (likuiditas 30 hari sebelum 4 Nov 2023).
