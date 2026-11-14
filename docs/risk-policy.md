# Kebijakan risiko

Semua batas di bawah diterapkan di kode (`bot/config.py`, `bot/engine.py`) dan dibuktikan lewat log (`data/raw/`).

| Kontrol | Nilai | Implementasi | Bukti di log |
|---|---|---|---|
| Long-only | tanpa short, margin, leverage | `strategy.evaluate` hanya mengembalikan BUY/SELL/HOLD atas posisi milik sendiri | `orders.jsonl` |
| Posisi terbuka maksimum | 4 (satu per pair, tanpa pyramiding) | `MAX_OPEN_POSITIONS` | event `entry_blocked` alasan `max_open_positions` |
| Ukuran per posisi | maks 10% ekuitas, dibatasi kas | `MAX_POSITION_FRACTION` | `notional` di `orders.jsonl` |
| Minimum order | Rp25.000 | `MIN_ORDER_IDR` | event `entry_blocked` |
| Daily loss limit | entry dihentikan bila ekuitas < 98% ekuitas awal hari WIB; exit tetap jalan | `DAILY_LOSS_LIMIT`; hari berganti 00:00 WIB = 17:00 UTC | event `daily_loss_limit_hit` |
| Ekuitas harian | diambil pada panggilan pertama setelah 00:00 WIB, dinilai di best bid | `engine.run_tick` | `equity_daily.jsonl` |
| Kill switch | Blob `kv/kill_switch.json` = `1`, atau env `KILL_SWITCH=1`; entry diblokir, exit tetap jalan; aktif tanpa redeploy lewat `scripts/kill_switch.py on` | `engine.kill_switch_on` | event `kill_switch_on/off/active` |
| Kegagalan storage saat membaca kill switch | dianggap aktif (fail-safe) | `engine.kill_switch_on` | — |
| Validasi data | entry ditolak bila: candle tertutup terakhir > 2× timeframe, ada candle hilang di jendela 300 candle, harga nol di jendela, volume nol pada candle keputusan, order book kosong, atau spread > 2% | `bot/validation.py` | event `data_invalid`, sinyal `INVALID` |
| Idempotency | setiap candle per pair diproses sekali (`last_processed`); panggilan ulang dicatat `dup:` | `engine._process_pair` | `processed` di `calls.jsonl` |
| Lock | satu panggilan pada satu waktu; lock basi > 240 detik dilepas | `storage.acquire_lock` | status `skipped_locked` |
| Timeout dan retry | timeout 10 detik, maksimal 3 percobaan, backoff 1,5 detik × n | `bot/indodax.get_json` | `errors.jsonl` (satu baris per percobaan gagal) |
| Endpoint | `/api/tick` menolak tanpa `Authorization: Bearer <CRON_SECRET>`; fail closed bila secret kosong | `bot/auth.py` | uji 401/200 |

## Hasil selama forward test (2026-11-04T05:00Z s/d 2026-11-14T05:00Z)

Dari `data/raw/` dan `data/dashboard_data.json`:

| Kejadian | Jumlah |
|---|---|
| Panggilan bot | 42 (semua `ok`) |
| Error API | 0 |
| Kill switch dipakai | 0 |
| Daily loss limit tersentuh | 0 |
| Data tidak valid | 0 |
| Entry diblokir | 0 |
| Pemrosesan pair-candle | 168 = 42 panggilan × 4 pair: 24 `processed` (6 candle × 4 pair, masing-masing tepat sekali) dan 144 `dup` (candle yang sama dipanggil lagi lalu dilewati) |

Uji fungsional kill switch, idempotency, lock, dan retry ada di `tests/test_core.py`.
