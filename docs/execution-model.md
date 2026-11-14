# Model eksekusi

Semua order adalah simulasi (dry run). Tidak ada API key dan tidak ada uang sungguhan. Sumber harga: API publik Indodax.

## Forward (bot live, `bot/engine.py` + `bot/execution.py`)

| Aspek | Aturan |
|---|---|
| Waktu sinyal | Close candle harian (1D, 00:00 UTC = 07:00 WIB). Candle yang masih berjalan dibuang: `Time + 86400 > server_time` |
| Waktu eksekusi | Pada panggilan bot pertama setelah candle ditutup. Jadwal cron 00:17 UTC, jadi delay normal sekitar 17 menit |
| Harga beli | Menyapu level **ask** dari order book saat itu sampai nominal terpenuhi; harga = VWAP level yang tersapu |
| Harga jual | Menyapu level **bid** sampai kuantitas habis; harga = VWAP |
| Dilarang | Fill di mid, last, atau close |
| Ukuran order | min(10% ekuitas, kas) ÷ (1 + fee) |
| Fee | Taker all-in 0,2222% di kedua sisi (`TAKER_FEE`; sumber di `FEES_SOURCES.md`) |
| Minimum order | Rp25.000 (lebih ketat dari `trade_min_base_currency` Rp10.000) |
| Pembulatan kuantitas | Dibulatkan ke bawah, 8 desimal (`quantity_increment` 1e-08) |
| Kedalaman kurang | Beli: sisa nominal tidak diisi. Jual: sisa kuantitas tetap sebagai posisi dan exit dicoba lagi di panggilan berikutnya |
| Penilaian ekuitas | Posisi terbuka × **best bid** saat itu |
| Dicatat per order | Waktu, pair, sisi, qty, best bid/ask, mid, VWAP, fee, harga sinyal, selisih vs sinyal, level tersapu, biaya spread+slippage |

## Backtest (`bot/backtest_core.py`)

Candle tidak berisi bid/ask, jadi biaya diambil dari snapshot order book yang diukur (`data/calibration.json`).

| Aspek | Aturan |
|---|---|
| Fungsi sinyal | `bot/strategy.py::evaluate`, fungsi yang sama dengan bot live |
| Waktu eksekusi | Open candle berikutnya |
| Harga beli | Open × (1 + half-spread + slip beli) |
| Harga jual | Open × (1 − half-spread − slip jual) |
| Half-spread, slip | Median per pair dari 9 snapshot asli sebelum cutoff 2026-11-10T00:17:24Z; slip = VWAP order referensi Rp10 juta vs best price |
| Penilaian ekuitas | Close × (1 − half-spread), sebagai proksi best bid |
| Fee, minimum, pembulatan | Sama dengan live |

## Dekomposisi biaya (setiap komponen dihitung sekali)

Untuk setiap trade tertutup:

- **Fee** = fee beli (dialokasikan ke kuantitas yang dijual) + fee jual.
- **Spread + slippage** = |VWAP − mid| × qty, di sisi beli dan sisi jual. Di backtest, mid diproksikan dengan Open.
- **Laba kotor** = (mid keluar − mid masuk) × qty, sebelum fee dan spread.
- **P/L bersih** = laba kotor − fee − spread/slippage. Rekonsiliasi backtest 3 tahun: Rp6.517.397 − Rp560.312 − Rp65.420 = Rp5.891.665, sama dengan Σ P/L terealisasi.
- **Porsi biaya** = (fee + spread + slippage) ÷ laba kotor. Bila laba kotor ≤ 0, rasio ini dilaporkan "tidak terdefinisi".

## Selisih forward vs backtest yang diharapkan

1. **Harga:** live mengeksekusi sekitar 17 menit setelah close di order book saat itu, sedangkan backtest memakai Open + biaya median.
2. **Spread:** median 9 snapshot kalibrasi bisa berbeda dari kondisi saat eksekusi (lihat panel spread di dashboard).
3. **Slippage ekor:** median slippage 0 untuk sebagian besar pair, padahal snapshot tertentu menunjukkan slip hingga 0,33% (XRP, jual Rp10 juta).
4. **Keterlambatan atau kegagalan jadwal:** candle yang tidak diproses sebelum candle berikutnya ditutup tidak dieksekusi di live.
