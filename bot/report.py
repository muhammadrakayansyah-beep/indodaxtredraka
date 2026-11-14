"""Render dashboard HTML mandiri (tanpa internet, tanpa library luar) dari output
bot.metrics.compute_all. Dipakai untuk dashboard.html offline dan /api/dashboard.
Tidak ada angka yang ditulis manual: semua berasal dari dict `D`."""
import base64
import html
import json
import os

AUTHOR_NAME = "Muhammad Rakah Yansyah"
AUTHOR_ID = "25120200002"
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


def logo_data_uri():
    """Logo disematkan sebagai data URI agar dashboard offline tetap mandiri."""
    try:
        with open(_LOGO_PATH, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return None

NA = "BELUM ADA DATA"


def pct(x, d=2):
    if x is None:
        return NA
    if isinstance(x, str):
        return x
    return f"{x * 100:,.{d}f}%".replace(",", "_").replace(".", ",").replace("_", ".")


def rp(x):
    if x is None:
        return NA
    return "Rp " + f"{x:,.0f}".replace(",", ".")


def num(x, d=2):
    if x is None:
        return NA
    if isinstance(x, str):
        return x.replace("_", " ")
    return f"{x:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def esc(x):
    return html.escape(str(x))


def svg_line(series, key="equity", color="var(--accent)", h=180):
    vals = [p[key] for p in series if p.get(key) is not None]
    if len(vals) < 2:
        return f'<p class="empty">{NA}</p>'
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1
    pts = " ".join(f"{i / (len(vals) - 1) * 1000:.1f},{h - 10 - (v - lo) / span * (h - 20):.1f}"
                   for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 1000 {h}" preserveAspectRatio="none" role="img" aria-label="kurva ekuitas">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" vector-effect="non-scaling-stroke" '
            f'points="{pts}"/></svg><div class="muted">min {rp(lo)} · maks {rp(hi)} · {len(vals)} titik</div>')


def card(label, value, note=""):
    n = f'<div class="note">{esc(note)}</div>' if note else ""
    return f'<div class="card"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>{n}</div>'


def table(headers, rows):
    if not rows:
        return f'<p class="empty">{NA}</p>'
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def trade_block(t):
    if not t:
        return f'<p class="empty">{NA}</p>'
    return '<div class="grid">' + "".join([
        card("Jumlah trade", t.get("trades", 0)),
        card("Win rate", pct(t.get("win_rate"))),
        card("Profit factor", num(t.get("profit_factor"))),
        card("Rata-rata untung", rp(t.get("avg_win"))),
        card("Rata-rata rugi", rp(t.get("avg_loss"))),
        card("Fee", rp(t.get("fees_idr"))),
        card("Spread + slippage", rp(t.get("spread_slippage_idr"))),
        card("Porsi biaya / laba kotor", pct(t.get("cost_share_of_gross")), t.get("cost_share_note") or ""),
    ]) + "</div>"


CSS = """
:root{--bg:#f6f7f9;--panel:#fff;--line:#dde2ea;--text:#111827;--muted:#5b6474;--accent:#0f7b6c;--warn:#8a5a00;--warnbg:#fff4dc;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#0b1220;--panel:#111c2e;--line:#26344a;--text:#e6edf7;--muted:#9aa9bd;--accent:#67e8c1;--warn:#ffd48a;--warnbg:#302610;--bad:#ff8290}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1180px;margin:auto;padding:24px 16px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:0 0 10px}h3{font-size:15px;margin:14px 0 8px}
.muted,.note{color:var(--muted)}.note{font-size:12px;margin-top:4px}.banner{margin:16px 0;padding:12px 14px;border:1px solid var(--warn);background:var(--warnbg);border-radius:10px;color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:10px 0}
.card,section{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.value{font-size:21px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
section{margin:14px 0}.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}th{color:var(--muted);font-weight:600}
svg{width:100%;height:180px;display:block}.empty{color:var(--warn)}code{font-size:13px}
.brand{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.logo{background:#fff;border-radius:10px;padding:6px 10px;display:inline-flex;border:1px solid var(--line)}.logo img{height:40px;width:auto;display:block}
.author{text-align:right}.author .nm{font-weight:700;font-size:15px}.author .id{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
@media(max-width:600px){.value{font-size:18px}.author{text-align:left}.logo img{height:32px}}
"""


def render(D):
    f = D.get("forward") or {}
    bf = D.get("backtest_full")
    sw = D.get("backtest_same_window")
    up = D.get("uptime") or {}
    ops = D.get("ops") or {}
    sm = D.get("signal_match")
    gap = D.get("gap")
    banner = []
    if not D.get("forward_complete"):
        banner.append("Forward test belum selesai: angka forward masih parsial.")
    if not bf:
        banner.append("Backtest penuh belum ada (data/backtest_full.json tidak ditemukan atau kalibrasi belum valid).")
    if not D.get("orders"):
        banner.append("Belum ada order simulasi pada jendela forward.")
    logo = logo_data_uri()
    logo_html = f'<span class="logo"><img src="{logo}" alt="rakahtrade"></span>' if logo else ""
    brand = (f'<div class="brand">{logo_html}<div class="author"><div class="nm">{esc(AUTHOR_NAME)}</div>'
             f'<div class="id">NIM {esc(AUTHOR_ID)}</div></div></div>')
    parts = [f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Dashboard Dry Run Indodax</title>
<style>{CSS}</style></head><body><main class="wrap">
{brand}<h1>Dashboard Dry Run Indodax</h1>
<div class="muted">Strategi {esc(D.get('strategy_version'))} · universe {esc(', '.join(D.get('universe', [])))} ·
jendela forward {esc(f.get('start'))} s/d {esc(f.get('end'))} (UTC) · dihitung {esc(D.get('generated_for_now'))} ·
semua angka dihasilkan oleh <code>scripts/hitung_ulang.py</code> dari log mentah.</div>"""]
    if banner:
        parts.append('<div class="banner">' + " ".join(esc(b) for b in banner) + "</div>")

    parts.append('<section><h2>Ringkasan</h2><div class="grid">' + "".join([
        card("Backtest penuh: return", pct(bf.get("total_return")) if bf else NA),
        card("Backtest penuh: CAGR", pct(bf.get("cagr")) if bf else NA),
        card("Backtest penuh: max DD", pct(bf.get("max_drawdown")) if bf else NA),
        card("Forward: return", pct(f.get("total_return"))),
        card("Forward: max DD", pct(f.get("max_drawdown"))),
        card("Backtest jendela sama: return", pct(sw.get("total_return")) if sw else NA),
        card("Gap return (forward - backtest)", pct(gap.get("forward_minus_backtest_return")) if gap else NA),
        card("Kecocokan sinyal", f"{sm['matched']}/{sm['compared']} = {pct(sm['match_rate'])}" if sm and sm["compared"] else NA),
    ]) + "</div></section>")

    parts.append("<section><h2>Benchmark buy &amp; hold BTC/IDR</h2><div class='grid'>" + "".join([
        card("Periode backtest penuh", pct((bf or {}).get("benchmark_btc_buy_hold", {}) and bf["benchmark_btc_buy_hold"].get("total_return")) if bf and bf.get("benchmark_btc_buy_hold") else NA),
        card("Jendela forward (backtest)", pct(sw["benchmark_btc_buy_hold"]["total_return"]) if sw and sw.get("benchmark_btc_buy_hold") else NA),
        card("Jendela forward (order book live)", pct(f["benchmark_btc_buy_hold"]["total_return"]) if f.get("benchmark_btc_buy_hold") else NA,
             "ask snapshot pertama → bid snapshot terakhir, termasuk fee"),
    ]) + "</div></section>")

    parts.append("<section><h2>Statistik trade</h2><h3>Forward test (log)</h3>" + trade_block(f) +
                 "<h3>Backtest jendela yang sama</h3>" + trade_block(sw) +
                 "<h3>Backtest penuh</h3>" + trade_block(bf) + "</section>")

    parts.append("<section><h2>Ekuitas</h2><h3>Forward (setiap panggilan, ditandai di best bid)</h3>" +
                 svg_line(D.get("forward_equity") or []) +
                 "<h3>Backtest penuh (mingguan)</h3>" + svg_line(D.get("backtest_full_curve") or []) +
                 "<h3>Ekuitas harian (panggilan pertama setelah 00:00 WIB)</h3>" +
                 table(["Hari WIB", "Waktu (UTC)", "Ekuitas", "Kas"],
                       [[e["day_wib"], e["ts"], rp(e["equity"]), rp(e["cash"])] for e in D.get("forward_equity_daily") or []]) +
                 "</section>")

    parts.append("<section><h2>Panel operasional</h2><div class='grid'>" + "".join([
        card("Uptime candle", pct(up.get("uptime")), f"{up.get('candles_on_time', 0)}/{up.get('candles_scheduled', 0)} candle tepat waktu"),
        card("Panggilan terlaksana", ops.get("calls_total", 0), f"perkiraan jadwal per jam: {ops.get('hourly_calls_expected', 0)}"),
        card("Panggilan OK / error", f"{ops.get('calls_ok', 0)} / {ops.get('calls_error', 0)}"),
        card("Error API (percobaan gagal)", ops.get("api_errors", 0)),
        card("Kill switch (on/off)", ops.get("kill_switch_events", 0), f"panggilan saat aktif: {ops.get('kill_switch_active_calls', 0)}"),
        card("Daily loss limit tersentuh", ops.get("daily_loss_limit_hits", 0)),
        card("Data tidak valid", ops.get("data_invalid_events", 0)),
        card("Entry diblokir", ops.get("entry_blocked_events", 0)),
    ]) + "</div>" + table(["Candle (UTC)", "Ditutup", "Batas", "Tepat waktu"] + D.get("universe", []),
                          [[r["candle_time"], r["closes_at"], r["deadline"], "ya" if r["ok"] else "tidak"] +
                           [r["per_pair"][p] for p in D.get("universe", [])] for r in up.get("rows", [])]) + "</section>")

    if sm:
        parts.append("<section><h2>Sinyal candle demi candle: forward vs backtest</h2>" +
                     table(["Pair", "Candle", "Forward", "Backtest", "Cocok", "Alasan forward", "Alasan backtest"],
                           [[r["pair"], r["candle_time"], r["live"] or "-", r["backtest"] or "-",
                             {True: "ya", False: "TIDAK", None: "-"}[r["match"]], r["live_reason"] or "",
                             r["backtest_reason"] or ""] for r in sm["rows"]]) + "</section>")

    yn = {True: "ya", False: "tidak", None: "-"}
    ls = D.get("latest_signals") or []
    no_fwd = "" if D.get("orders") else (
        "<p class='empty'>Tidak ada order forward: syarat entry (RSI(4) &lt; 10, close &gt; SMA200, "
        "SMA50 &gt; SMA200) tidak pernah terpenuhi bersamaan pada candle yang diproses. "
        "Tabel di bawah adalah sinyal terakhir per pair dari log.</p>" +
        table(["Pair", "Candle", "Aksi", "RSI(4)", "RSI<10", "Close>SMA200", "SMA50>SMA200"],
              [[r["pair"], r.get("candle_time", NA), r.get("action", NA), num(r.get("rsi"), 1),
                yn[r.get("cond_rsi")], yn[r.get("cond_close_sma200")], yn[r.get("cond_sma50_sma200")]] for r in ls]))
    parts.append("<section><h2>Order simulasi (forward)</h2>" + no_fwd +
                 table(["Waktu", "Pair", "Sisi", "Qty", "Best bid", "Best ask", "Avg fill", "Fee", "Harga sinyal", "Selisih vs sinyal", "P/L"],
                       [[o["ts"], o["pair"], o["side"], num(o["qty"], 8), num(o["best_bid"], 0), num(o["best_ask"], 0),
                         num(o["avg_fill"], 2), rp(o["fee"]), num(o["signal_price"], 0), pct(o["diff_vs_signal_pct"], 3),
                         rp(o.get("realized_pnl")) if o["side"] == "SELL" else ""] for o in D.get("orders") or []]) +
                 "<h3>Dekomposisi selisih fill</h3>" +
                 table(["Waktu", "Pair", "Sisi", "Spread saat fill", "Slippage vs best", "Gerak mid vs sinyal", "Delay (menit)", "Fill backtest", "Gap fill"],
                       [[r["ts"], r["pair"], r["side"], pct(r["spread_pct_at_fill"], 3), pct(r["slippage_vs_best_pct"], 3),
                         pct(r["mid_move_vs_signal_pct"], 3),
                         num(r["delay_from_candle_close_s"] / 60, 1) if r.get("delay_from_candle_close_s") is not None else NA,
                         num(r.get("backtest_fill"), 2) if r.get("backtest_fill") else NA, pct(r.get("fill_gap_pct"), 3)]
                        for r in D.get("fill_gaps") or []]) + "</section>")

    ep = D.get("execution_probe") or []
    parts.append("<section><h2>Uji eksekusi di order book asli</h2>"
                 "<p class='muted'>Bukan trade dan tidak memengaruhi ekuitas. Order sebesar ukuran posisi strategi "
                 "(10% modal) disimulasikan menyapu snapshot order book terakhir di jendela forward: beli di ask, "
                 "jual kembali di bid, termasuk fee taker. Menunjukkan biaya eksekusi nyata bila sinyal muncul.</p>" +
                 table(["Pair", "Snapshot (UTC)", "Order", "Best bid", "Best ask", "Spread", "VWAP beli", "Slip beli",
                        "VWAP jual", "Slip jual", "Level beli/jual", "Biaya bolak-balik"],
                       [[r["pair"], r.get("snapshot_ts") or NA, rp(r.get("order_idr")), num(r.get("best_bid"), 0),
                         num(r.get("best_ask"), 0), pct(r.get("spread_pct"), 4), num(r.get("buy_vwap"), 2),
                         pct(r.get("buy_slip_pct"), 4), num(r.get("sell_vwap"), 2), pct(r.get("sell_slip_pct"), 4),
                         f"{r.get('buy_levels', '-')}/{r.get('sell_levels', '-')}",
                         f"{rp(r.get('roundtrip_cost_idr'))} ({pct(r.get('roundtrip_cost_pct'), 3)})"]
                        for r in ep if r.get("snapshot_ts")]) + "</section>")

    bo = D.get("backtest_orders") or []
    parts.append("<section><h2>Order simulasi backtest (3 tahun)</h2>"
                 "<p class='muted'>Dari <code>data/backtest_full_orders.csv</code> (scripts/backtest.py): "
                 "eksekusi di Open candle berikutnya ± half-spread + slippage hasil kalibrasi, fee taker.</p>" +
                 table(["Tanggal (UTC)", "Pair", "Sisi", "Alasan", "Harga sinyal", "Open", "Harga fill", "Qty", "Fee", "P/L"],
                       [[str(o.get("time", ""))[:10], o.get("pair"), o.get("side"), o.get("reason"),
                         num(o.get("signal_price"), 0), num(o.get("open"), 0), num(o.get("price"), 2),
                         num(o.get("qty"), 8), rp(o.get("fee")),
                         rp(o.get("realized_pnl")) if o.get("side") == "SELL" else ""] for o in bo]) + "</section>")

    sc = D.get("spread_comparison") or {}
    rows = []
    for p in D.get("universe", []):
        cu = (sc.get("calibration_used") or {}).get(p, {})
        pre = (sc.get("pre_freeze") or {}).get(p, {})
        al = (sc.get("all_snapshots") or {}).get(p, {})
        rows.append([p, pct(cu.get("half_spread"), 4), cu.get("n", NA), pct(pre.get("half_spread"), 4), pre.get("n", 0),
                     pct(al.get("half_spread"), 4), al.get("n", 0), pct(cu.get("buy_slip"), 4), pct(al.get("buy_slip"), 4)])
    parts.append("<section><h2>Spread &amp; slippage: backtest vs seluruh snapshot</h2>" +
                 table(["Pair", "Half-spread backtest", "n kalibrasi", "Half-spread pra-start", "n", "Half-spread semua", "n",
                        "Slip beli backtest", "Slip beli semua"], rows) +
                 "<p class='muted'>Slippage = order referensi Rp10 juta menyapu buku, relatif terhadap best price.</p></section>")

    parts.append("<section><h2>Event &amp; error terakhir</h2>" +
                 table(["Waktu", "Tipe", "Detail"], [[e.get("ts"), e.get("type"),
                       json.dumps({k: v for k, v in e.items() if k not in ("ts", "type", "call_id")}, ensure_ascii=False)[:200]]
                       for e in (D.get("events_sample") or [])[-25:]]) +
                 table(["Waktu", "URL", "Percobaan", "Error"], [[e.get("ts"), e.get("url"), e.get("attempt"), e.get("error")]
                       for e in (D.get("errors_sample") or [])[-25:]]) + "</section>")

    payload = json.dumps(D, ensure_ascii=False, separators=(",", ":"), default=str).replace("</", "<\\/")
    parts.append(f'<script type="application/json" id="dashboard-data">{payload}</script></main></body></html>')
    return "".join(parts)


def extract_data(html_text):
    start = html_text.index('id="dashboard-data">') + len('id="dashboard-data">')
    end = html_text.index("</script>", start)
    return json.loads(html_text[start:end].replace("<\\/", "</"))
