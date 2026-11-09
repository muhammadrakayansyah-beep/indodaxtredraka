"""Parameter strategi, universe, eksekusi, dan risiko.

SEMUA nilai di file ini ikut dibekukan pada commit freeze. Mengubah file ini
setelah freeze = mengubah aturan (lihat FREEZE.md). Perbaikan bug yang tidak
mengubah aturan dilakukan di file lain dan dicatat lewat scripts/log_bugfix.py.
"""

STRATEGY_VERSION = "mr-rsi4-sma200-v1"

# ---------------------------------------------------------------- universe
# Kandidat universe. Lihat STRATEGI.md bagian survivorship bias dan
# scripts/universe_selection.py untuk prosedur seleksi point-in-time.
UNIVERSE = ["BTCIDR", "ETHIDR", "XRPIDR", "DOGEIDR"]
BENCHMARK_SYMBOL = "BTCIDR"

# ---------------------------------------------------------------- timeframe
TIMEFRAME = "1D"            # parameter tf history_v2
TF_SECONDS = 86400          # candle 1D Indodax: 00:00 UTC s/d 00:00 UTC (07:00 WIB)

# ---------------------------------------------------------------- strategi (dari UTS, default Mean Reversion)
RSI_PERIOD = 4              # RSI Wilder
RSI_ENTRY_BELOW = 10.0      # entry jika RSI < 10
SMA_FAST = 50
SMA_SLOW = 200
TAKE_PROFIT_PCT = 0.03      # close >= harga referensi entry * (1 + 3%)
TIME_STOP_BARS = 40         # keluar setelah 40 candle penuh
# Indikator SELALU dihitung dari tepat INDICATOR_WINDOW candle tertutup terakhir,
# di backtest maupun bot, supaya RSI Wilder (yang bergantung titik awal) identik.
INDICATOR_WINDOW = 300

# ---------------------------------------------------------------- sizing & risiko
INITIAL_CAPITAL_IDR = 100_000_000.0
MAX_OPEN_POSITIONS = 4
MAX_POSITION_FRACTION = 0.10      # maks 10% ekuitas per posisi baru
DAILY_LOSS_LIMIT = 0.02           # stop entry jika ekuitas < 98% ekuitas awal hari WIB
WIB_OFFSET_SECONDS = 7 * 3600     # batas hari 00:00 WIB = 17:00 UTC

# ---------------------------------------------------------------- eksekusi & biaya
# Fee taker all-in. /api/pairs (diakses 2026-11-09) trade_fee_percent_taker = 0.2
# untuk BTCIDR/ETHIDR/XRPIDR/DOGEIDR. STRATEGI.md mencatat halaman resmi
# "Rincian Biaya Transaksi" (help.indodax.com) menyebut contoh all-in 0,2222%.
# Aturan tugas: pakai yang lebih mahal -> 0.2222%.
# !! Angka 0,2222% BELUM diverifikasi ulang di repositori ini: cek halaman resmi,
# !! catat URL + tanggal akses di FEES_SOURCES.md sebelum freeze.
TAKER_FEE = 0.002222
MIN_ORDER_IDR = 25_000.0          # lebih ketat dari trade_min_base_currency (Rp10.000)
QTY_DECIMALS = 8                  # quantity_increment 1e-08 di /api/pairs

# Validasi data
MAX_SPREAD_PCT = 0.02             # tolak entry bila (ask-bid)/mid > 2%
STALE_FACTOR = 2                  # candle tertutup terakhir > 2x timeframe = basi
ORDERBOOK_LEVELS_TO_STORE = 50    # level per sisi yang disimpan di snapshot
SLIPPAGE_REF_ORDER_IDR = 10_000_000.0  # order referensi untuk ukur slippage
MIN_SNAPSHOTS_PER_PAIR = 9        # kalibrasi backtest ditolak bila kurang

# ---------------------------------------------------------------- HTTP
HTTP_TIMEOUT_S = 10
HTTP_MAX_RETRIES = 3              # retry terbatas
HTTP_BACKOFF_S = 1.5
LOCK_TTL_S = 240                  # < batas 300 detik Vercel Hobby

# ---------------------------------------------------------------- jendela forward test
# Jadwal resmi soal: 2026-11-04 12:00 WIB s/d 2026-11-14 12:00 WIB.
# Jika dosen menyetujui recovery/late run, GANTI dua nilai ini di commit freeze
# baru (waktu sebenarnya), jangan dimundurkan ke tanggal lampau.
FORWARD_START_UTC = "2026-11-04T05:00:00Z"
FORWARD_END_UTC = "2026-11-14T05:00:00Z"

REDIS_PREFIX = "indodax-dryrun:"
