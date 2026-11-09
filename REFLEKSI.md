# Refleksi — draf yang belum bisa difinalkan

**Bukan refleksi hasil akhir.** Pada 9 Nov 2026 belum ada bukti deploy atau log forward test. Jendela yang ditentukan dosen berakhir 14 Nov; angka forward return, drawdown, uptime, selisih fill, dan gap backtest tidak tersedia dan sengaja tidak diisi. Jangan serahkan dokumen ini sebagai refleksi final tanpa melengkapi bagian setelah pengujian benar-benar selesai.

## Keterbatasan yang sudah terverifikasi

- ZIP sumber UTS tidak memuat `.git`, jadi commit freeze asli tidak bisa diverifikasi dari bahan yang diberikan.
- Tidak ada snapshot order book pra-freeze. Empat snapshot pada 9 Nov hanya menunjukkan API publik dapat diakses; empat titik ini tidak cukup untuk mengkalibrasi median spread/slippage. Backtest berhenti sebelum menghasilkan angka.
- Universe empat pasangan saat ini belum diuji terhadap kriteria likuiditas point-in-time pada awal periode. Daftar pasangan terkini saja berisiko survivorship bias.
- Bot belum dideploy dan belum mengalami jadwal Vercel/Upstash. Karena itu stabilitas, uptime, timeout platform, dan persistence belum terbukti.
- Karena forward log belum tersedia, dashboard menyatakan data belum ada alih-alih menampilkan hasil simulasi buatan.

## Bagian yang harus diisi dari hitung ulang log

Setelah test yang disetujui dosen benar-benar berakhir, jalankan `scripts/export_logs.py` lalu `scripts/hitung_ulang.py` dan hitung ulang backtest penuh serta backtest pada jendela tanggal identik dari candles Indodax. Gunakan `data/dashboard_data.json` (berisi backtest penuh, backtest jendela sama, forward, uptime, kecocokan sinyal); jangan mengetik angka langsung ke HTML.

- Backtest penuh: return total __ ; CAGR __ ; max drawdown __ ; trade __ ; benchmark BTC buy & hold __.
- Backtest jendela forward yang sama: return __ ; max drawdown __ ; trade __ ; benchmark BTC buy & hold __.
- Forward: return __ ; max drawdown __ ; trade tertutup __ ; win rate __ ; profit factor __.
- Uptime: candle unik terproses __ / candle terjadwal __ = __ ; error API __ ; kill-switch __.
- Biaya eksekusi yang dihitung dari raw log: fee __ IDR; spread/slippage __ IDR; porsi biaya terhadap laba kotor __.
- Perubahan sinyal candle demi candle pada replay: __. Jelaskan setiap perbedaan dengan timestamp/candle, bukan dugaan umum.
- Selisih fill: untuk setiap order, rekonsiliasi harga sinyal, best bid/ask, VWAP fill, biaya dan delay scheduler. Lampirkan sumber log.

## Interpretasi yang diharapkan

Jika sinyal sama tetapi return berbeda, pisahkan efek timing jadwal, harga book aktual, spread/slippage, biaya, partial fill, dan equity marking pada bid. Bila sinyal berbeda, audit versi fungsi strategi, candle yang belum tutup/hilang, timezone, atau kesalahan idempotency sebelum menjelaskan performa. Hasil buruk tetap dilaporkan; tidak ada angka yang boleh disesuaikan manual.
