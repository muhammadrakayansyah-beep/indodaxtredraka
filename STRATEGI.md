# Strategi dry-run Indodax — kandidat recovery

**Status: belum dibekukan; parameter di bawah adalah kandidat rekonstruksi, bukan bukti parameter yang di-commit sebelum 4 Nov 2026.**

## Asal strategi dan perubahan

Strategi mengambil default Mean Reversion dari artefak UTS yang dikirim: RSI Wilder(4) < 10, harga close di atas SMA(200), SMA(50) di atas SMA(200), sizing 10% ekuitas/slot, target 3%, time stop 40 bar, dan exit saat death cross fast/slow. UTS memakai saham harian dan eksekusi open bar berikutnya. Untuk port kripto, timeframe tetap 1 hari dan sinyal hanya dihitung dari candle Indodax yang sudah tutup.

Perubahan teknis untuk dry-run: (1) satu posisi maksimum per pasangan; (2) maksimum 4 posisi, masing-masing maksimum 10% ekuitas; (3) order simulasi beli menyapu ask dan jual menyapu bid dari snapshot saat eksekusi; (4) taker fee konservatif 0,2222% kedua sisi; (5) minimum order langsung Pro Rp25.000; (6) daily loss limit 2% dan kill switch Redis; (7) daily candle Indodax berakhir 00:00 UTC / 07:00 WIB dan cron disetel 07:15 WIB.

Perubahan ini belum dapat dianggap selesai sebelum freeze date: artefak awal tidak berisi `.git`, log snapshots pra-freeze, atau deployment. Jangan menulis seolah-olah perubahan ini terjadi sebelum freeze.

## Aturan sinyal

Indikator dihitung dari close candle harian yang lengkap, **selalu dari tepat 300 candle tertutup terakhir** (`INDICATOR_WINDOW`), di backtest maupun bot. RSI Wilder bergantung pada titik awal; jendela tetap membuat nilainya identik di kedua tempat. Fungsi sinyal tunggal: `bot/strategy.py::evaluate`.

- Entry long jika sekaligus `close > SMA(200)`, `SMA(50) > SMA(200)`, dan RSI Wilder(4) `< 10`.
- Tidak ada short, margin, leverage, pyramiding, atau pembelian berulang pada candle yang sama.
- Keluar jika close mencapai 3% di atas harga referensi masuk (= **Open candle setelah candle sinyal**, sama dengan eksekusi UTS di open bar berikutnya; diambil dari data candle, bukan dari harga fill, agar backtest dan bot memberi sinyal identik), posisi telah mencapai 40 candle penuh, atau SMA(50) menyeberang dari atas ke bawah SMA(200).
- Sinyal exit berasal dari close; live dry-run mengeksekusi setelah sinyal pada best bid saat cron berikutnya berjalan. Backtest mengeksekusi pada open bar berikutnya, dengan spread/slippage hasil pengukuran dan fee.
- Bila belum tersedia 300 candle, ada candle hilang pada jendela indikator, candle terbaru belum tertutup/kedaluwarsa (>2× timeframe), harga nol di jendela, volume nol pada candle keputusan, order book kosong, atau spread >2%, pasangan ditolak dan alasannya dicatat.

## Sizing dan batas risiko

- Modal simulasi: Rp100.000.000.
- Maksimum 4 posisi terbuka; posisi baru dibatasi 10% dari ekuitas saat itu, termasuk kecukupan saldo kas. Setiap order juga harus ≥Rp25.000.
- Daily loss limit: penurunan 2% terhadap ekuitas awal hari WIB (00:00 WIB); bila terlewati, tidak ada entry baru sampai hari WIB selanjutnya. Exit tetap diproses.
- Kill switch tersimpan sebagai key `indodax-dryrun:kill_switch` di Upstash Redis. Nilai `1`/`true`/`on`/`yes` menghentikan entry tanpa redeploy, namun exit tetap aktif. Aktivasi tercatat.
- Semua state dan log berada di Upstash; state filesystem serverless tidak diandalkan. Lock Redis mencegah dua invocation berjalan bersamaan; status candle terakhir mencegah pemrosesan ganda.

## Universe dan survivorship bias

Kandidat konfigurasi: BTCIDR, ETHIDR, XRPIDR, DOGEIDR. Keempatnya ada pada API pairs saat pemeriksaan 9 Nov 2026 dan memiliki data harian Indodax sejak 3 Nov 2023 pada respons yang diunduh. Namun kandidat ini **belum memenuhi bukti pemilihan point-in-time**: belum dibuktikan bahwa empat pasangan dipilih berdasarkan likuiditas yang diukur pada awal periode, dan daftar `/api/pairs` saat ini saja akan menimbulkan survivorship bias. Kriteria yang seharusnya dipakai sebelum freeze: dari semua pair IDR yang benar-benar tersedia pada 4 Nov 2023, pilih 3–10 pasangan menurut median nilai transaksi IDR 30 hari terakhir sebelum tanggal itu, lalu simpan daftar sumber, timestamp, perhitungan, dan daftar pair termasuk yang dikeluarkan. File ini tidak mengklaim langkah tersebut telah dilakukan.

## Eksekusi dan biaya

Order masuk menggunakan ask, order keluar menggunakan bid, dan kuantitas menyapu level yang tersedia sampai penuh. Bila kedalaman snapshot tidak mencukupi, sisa tidak diisi dan dicatat. Harga mid/close tidak dipakai sebagai fill. Biaya taker kandidat 0,2222% pada beli dan jual; nilai `/api/pairs` saat pemeriksaan menunjukkan 0,20% untuk pasangan contoh, sedangkan halaman biaya Indodax mencantumkan contoh all-in taker 0,2222%. Mengikuti aturan tugas, nilai lebih tinggi dipakai. Verifikasi ulang fee dan minimum langsung Pro pada tanggal freeze diperlukan.

Backtest hanya menerima kalibrasi yang dibuat dari raw snapshots dengan minimal 9 snapshot valid per pair (4 pair = minimal 36 titik); slippage diukur dari order referensi Rp10 juta terhadap mid di seluruh level buku. Snapshot yang ada sekarang hanya satu tiap pair pada 9 Nov, selepas freeze. Itu belum cukup untuk kalibrasi yang patuh aturan dan tidak mewakili spread masa lampau. Karena itu tidak ada backtest return yang dilaporkan dari biaya buatan/default.

## Universe dan parameter untuk dibekukan bila dosen mengizinkan late/recovery run

Sebelum freeze baru yang disetujui dosen, commit dan push bersama parameter `bot/config.py`, universe serta cara seleksinya, sumber fee/minimum, jadwal mulai/akhir, digest berkas candles/snapshot, versi kode, dan hash commit. Jangan force-push. Jika strategi berubah, catat perubahan sebagai versi baru dan jangan bandingkan dengan log versi sebelumnya seolah-olah setara.

## Catatan implementasi (ditambahkan 9 Nov 2026, sebelum freeze baru)

Bagian ini mencatat keputusan yang dibuat saat kode bot ditulis. Semuanya **belum** dibekukan.

1. **Harga referensi take-profit** = Open candle setelah candle sinyal (lihat aturan sinyal).
2. **Jendela indikator tetap 300 candle** (lihat aturan sinyal).
3. **Aturan volume nol diperjelas.** Candle harian Indodax asli (ditarik 9 Nov 2026) memuat volume 0 pada 2024-09-12 untuk BTCIDR, ETHIDR, XRPIDR, DOGEIDR, dan juga 2024-09-13 untuk ETHIDR, XRPIDR, DOGEIDR. Pada hari-hari itu O=C dan sama dengan close sebelumnya. Penyebabnya belum diverifikasi di repositori ini. Jika volume nol diperiksa di seluruh jendela 300 candle, satu hari itu memblokir sinyal ~300 hari. Karena itu volume nol hanya diperiksa pada candle keputusan, sedangkan harga nol tetap diperiksa di seluruh jendela.
4. **Penjadwal.** GitHub Actions memanggil `/api/tick` tiap jam di menit ke-17. Vercel Cron harian 00:17 UTC (07:17 WIB) menjadi cadangan. Candle harian diproses sekali saja (idempotent); panggilan lainnya menyimpan snapshot order book (≥24/hari) dan memberi banyak kesempatan agar candle terproses sebelum candle berikutnya ditutup.
5. **Uptime** = candle harian di jendela forward yang sinyal valid-nya tercatat untuk *semua* pair sebelum candle berikutnya ditutup ÷ jumlah candle tertutup di jendela. Jumlah panggilan per jam dilaporkan terpisah.
6. **Daily loss limit di backtest** adalah aproksimasi. Candle harian tidak punya titik 00:00 WIB, jadi entry pada open t diblokir bila ekuitas close t-1 < 98% ekuitas close t-2. Bot live memakai batas hari WIB yang sebenarnya.
7. **Laba kotor** untuk porsi biaya = Σ (mid keluar − mid masuk) × qty pada trade tertutup. Untuk backtest, mid diproksikan dengan Open. Bila laba kotor ≤ 0, rasio dilaporkan "tidak terdefinisi" (bukan dipaksakan).
8. **Exit tetap diproses** saat kill switch, daily loss limit, atau spread >2% (dicatat sebagai event). Bila order book kosong atau kedalaman kurang, exit ditunda dan dicoba ulang di panggilan berikutnya.

## Hasil uji universe point-in-time (dijalankan 14 Nov 2026)

`scripts/universe_selection.py --asof 2023-11-04 --top 4` → `data/universe_selection.json`. Peringkat median nilai transaksi IDR harian, 30 hari sebelum 4 Nov 2023: USDTIDR, BTCIDR, ETHIDR, XRPIDR, DOGEIDR, SOLIDR, dan seterusnya. Universe bot (BTC, ETH, XRP, DOGE) = peringkat 2–5, yaitu 4 teratas tanpa stablecoin. Pengecualian stablecoin dirumuskan ex post; lihat REFLEKSI.md bagian 5 poin 7.
