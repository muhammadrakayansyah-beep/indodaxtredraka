# Definisi metrik

Semua metrik dihitung oleh `bot/metrics.py`. Modul itu dipakai bersama oleh `scripts/hitung_ulang.py` (dashboard offline) dan `api/dashboard.py` (dashboard Vercel), jadi rumusnya identik di keduanya.

| Metrik | Definisi | Catatan |
|---|---|---|
| Return total | ekuitas akhir ÷ ekuitas awal − 1 | Sudah setelah fee dan spread/slippage. Forward: ekuitas dari panggilan terakhir di jendela, dinilai di best bid |
| CAGR | (ekuitas akhir ÷ awal)^(1/tahun) − 1; tahun = durasi tepat ÷ 365,25 hari | Hanya untuk backtest; **tidak** ditampilkan untuk forward |
| Max drawdown | min(ekuitas_t ÷ puncak sebelumnya − 1) | Forward: deret ekuitas setiap panggilan. Backtest: ekuitas harian di Close × (1 − half-spread) |
| Trade | jumlah order SELL (trade tertutup) | Posisi terbuka di akhir periode tidak dihitung sebagai trade |
| Win rate | trade dengan P/L bersih > 0 ÷ semua trade | Trade impas (P/L = 0) dihitung **kalah** |
| Profit factor | Σ P/L trade untung ÷ \|Σ P/L trade rugi\| | Tanpa trade rugi → ditampilkan "tak hingga (tanpa rugi)"; tanpa trade → tidak terdefinisi |
| Rata-rata untung / rugi | rata-rata P/L bersih per trade untung / rugi, setelah fee | |
| Laba kotor | Σ (mid keluar − mid masuk) × qty pada trade tertutup | Backtest: mid = Open |
| Porsi biaya | (fee + spread + slippage) ÷ laba kotor | Bila laba kotor ≤ 0 → "tidak terdefinisi" |
| Biaya spread + slippage | \|VWAP − mid\| × qty per sisi | Satu angka gabungan terhadap mid, sehingga spread dan slippage tidak terhitung dua kali |
| Buy & hold BTC (backtest) | beli di Open pertama × (1 + half-spread + slip) + fee, jual di Close terakhir × (1 − half-spread − slip) − fee | Modal sama Rp100 juta |
| Buy & hold BTC (forward) | best ask snapshot pertama di jendela → best bid snapshot terakhir, fee taker di kedua sisi | |
| Kecocokan sinyal | aksi live = aksi replay backtest, per pair per candle | Candle yang dibandingkan adalah candle yang diproses live; replay dimulai flat |
| Uptime | candle forward yang sinyal valid-nya tercatat untuk **semua** pair sebelum candle berikutnya ditutup ÷ candle forward yang sudah ditutup | Sesuai definisi soal |
| Drift cron | waktu mulai sebenarnya − menit ke-17 jam terjadwal | Dari `calls.jsonl` |
| Uji eksekusi | order 10% modal menyapu snapshot terakhir: beli di ask, jual di bid, termasuk fee | **Bukan trade**; tidak memengaruhi ekuitas |

Verifikasi: `python scripts/hitung_ulang.py --verify dashboard.html` membandingkan seluruh angka yang tertanam di HTML dengan hasil hitung ulang dari log mentah. Toleransinya 1e-9 relatif untuk bilangan desimal; nilai lain harus sama persis.
