"""Tes tambahan mengikuti kelas tes di blueprint (bagian 13): eksekusi, invarian,
risiko, data, resiliensi, paritas, dan rekonsiliasi. Tidak mengubah kode bot."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from bot import backtest_core as BT  # noqa: E402
from bot import config as C  # noqa: E402
from bot import engine, execution as X, indodax as API, storage, strategy as S, validation as V  # noqa: E402

DAY = 86400


def mk(closes, t0=1_790_000_000 // DAY * DAY, vol=1.0):
    return [{"Time": t0 + i * DAY, "Open": c, "High": c, "Low": c, "Close": c, "Volume": vol}
            for i, c in enumerate(closes)]


BUY_CLOSES = [100 + i * 0.5 for i in range(296)] + [240, 230, 220, 210]


class Execution(unittest.TestCase):
    def test_zero_liquidity(self):
        self.assertIsNone(X.sweep_buy_idr([], 1_000_000))
        self.assertIsNone(X.sweep_sell_qty([], 1.0))
        self.assertIsNone(X.book_stats({"bids": [], "asks": [[1, 1]]}))

    def test_insufficient_depth_partial_buy(self):
        f = X.sweep_buy_idr([[100.0, 1.0]], 500.0)
        self.assertAlmostEqual(f["qty"], 1.0)
        self.assertAlmostEqual(f["unfilled_idr"], 400.0)

    def test_fill_qty_never_exceeds_request(self):
        f = X.sweep_sell_qty([[100.0, 5.0], [99.0, 5.0]], 3.0)
        self.assertLessEqual(f["qty"], 3.0)

    def test_vwap_multi_level(self):
        f = X.sweep_sell_qty([[100.0, 1.0], [90.0, 1.0]], 2.0)
        self.assertAlmostEqual(f["vwap"], 95.0)

    def test_spread_above_2pct_rejected(self):
        st = X.book_stats({"bids": [[97.0, 1]], "asks": [[100.0, 1]]})
        self.assertTrue(any("spread" in p for p in V.book_problems(st)))

    def test_crossed_book_rejected(self):
        st = X.book_stats({"bids": [[101.0, 1]], "asks": [[100.0, 1]]})
        self.assertTrue(V.book_problems(st))

    def test_quantity_rounded_down_8_decimals(self):
        self.assertEqual(X.floor_qty(0.123456789), 0.12345678)


class Data(unittest.TestCase):
    def test_closed_candle_boundary(self):
        cs = mk([1, 2, 3])
        # tepat Time + tf == server_time -> sudah tertutup
        self.assertEqual(len(API.closed_only(cs, cs[-1]["Time"] + DAY, DAY)), 3)
        self.assertEqual(len(API.closed_only(cs, cs[-1]["Time"] + DAY - 1, DAY)), 2)

    def test_stale_window(self):
        w = mk([100.0] * 300)
        now = w[-1]["Time"] + DAY + 2 * DAY + 1
        self.assertTrue(any("basi" in p for p in V.window_problems(w, now)))

    def test_gap_detected(self):
        w = mk([100.0] * 301)
        del w[150]
        self.assertTrue(any("hilang" in p for p in V.window_problems(w[-300:])))

    def test_zero_volume_on_decision_candle(self):
        w = mk([100.0] * 300)
        w[-1]["Volume"] = 0.0
        self.assertTrue(V.window_problems(w))
        w2 = mk([100.0] * 300)
        w2[10]["Volume"] = 0.0   # volume nol di tengah jendela tidak memblokir (STRATEGI.md)
        self.assertEqual(V.window_problems(w2), [])


class Resilience(unittest.TestCase):
    def _urlopen_returning(self, body):
        class R:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def read(self_):
                return body
        return mock.patch("urllib.request.urlopen", return_value=R())

    def test_malformed_json(self):
        with self._urlopen_returning(b"{not json"), mock.patch("time.sleep"):
            with self.assertRaises(API.ApiError):
                API.get_json("/api/server_time", [])

    def test_empty_response(self):
        with self._urlopen_returning(b""), mock.patch("time.sleep"):
            with self.assertRaises(API.ApiError):
                API.get_json("/api/server_time", [])


class Risk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cs = mk(BUY_CLOSES + [999])
        self.now = self.cs[-1]["Time"] + 900

    def _run(self, store, book=None, now=None):
        book = book or {"bids": [[209.0, 1e6]], "asks": [[210.0, 1e6]]}
        with mock.patch.object(API, "server_time", return_value=now or self.now), \
                mock.patch.object(API, "depth", return_value=book), \
                mock.patch.object(API, "history", return_value=list(self.cs)):
            return engine.run_tick(store, "test")

    def test_max_open_positions(self):
        st = storage.LocalStore(os.path.join(self.tmp, "a.json"))
        with mock.patch.object(C, "MAX_OPEN_POSITIONS", 2):
            self._run(st)
        self.assertEqual(len([o for o in st.read_stream("orders") if o["side"] == "BUY"]), 2)
        reasons = [r for e in st.read_stream("events") if e["type"] == "entry_blocked" for r in e["reasons"]]
        self.assertIn("max_open_positions", reasons)

    def test_cash_never_negative_and_size_cap(self):
        st = storage.LocalStore(os.path.join(self.tmp, "b.json"))
        self._run(st)
        state = json.loads(st.get("state"))
        self.assertGreaterEqual(state["cash"], 0)
        for o in st.read_stream("orders"):
            self.assertLessEqual(o["notional"] + o["fee"], C.MAX_POSITION_FRACTION * C.INITIAL_CAPITAL_IDR + 1e-6)

    def test_wide_spread_blocks_entry(self):
        st = storage.LocalStore(os.path.join(self.tmp, "c.json"))
        self._run(st, book={"bids": [[200.0, 1e6]], "asks": [[210.0, 1e6]]})
        self.assertEqual(st.read_stream("orders"), [])

    def test_daily_loss_limit_and_wib_reset(self):
        st = storage.LocalStore(os.path.join(self.tmp, "d.json"))
        state = engine.new_state()
        state.update(day=engine.wib_day(self.now), day_start_equity=200_000_000.0, created_at="x")
        st.set("state", json.dumps(state))
        self._run(st)
        types = [e["type"] for e in st.read_stream("events")]
        self.assertIn("daily_loss_limit_hit", types)
        self.assertEqual(st.read_stream("orders"), [])
        # hari WIB berikutnya: batas direset, ekuitas harian baru dicatat
        self.cs = mk(BUY_CLOSES + [210, 999])
        self._run(st, now=self.cs[-1]["Time"] + 900)
        s2 = json.loads(st.get("state"))
        self.assertFalse(s2["daily_halt"])
        self.assertEqual(len(st.read_stream("equity_daily")), 1)


class Parity(unittest.TestCase):
    def test_backtest_and_direct_evaluate_agree_on_real_candles(self):
        path = os.path.join(ROOT, "data", "candles", "BTCIDR_1D.json")
        if not os.path.exists(path):
            self.skipTest("data candle tidak ada")
        cs = json.load(open(path))["candles"]
        calib = {p: {"half_spread": 0.0, "buy_slip": 0.0, "sell_slip": 0.0} for p in C.UNIVERSE}
        t0, t1 = cs[-120]["Time"], cs[-1]["Time"]
        res = BT.run({"BTCIDR": cs}, calib, t0, t1, universe=["BTCIDR"])
        idx = {c["Time"]: i for i, c in enumerate(cs)}
        checked = 0
        for s in res["signals"]:
            if s.get("had_position") or "action" not in s or s["action"] == "INVALID":
                continue
            i = idx[s["candle_time"]]
            d = S.evaluate(cs[i - C.INDICATOR_WINDOW + 1: i + 1], None)
            self.assertEqual(d["action"], s["action"])
            checked += 1
        self.assertGreater(checked, 50)


class Schedule(unittest.TestCase):
    def test_cron_constants_match_vercel_json(self):
        from bot import metrics as M
        crons = json.load(open(os.path.join(ROOT, "vercel.json")))["crons"]
        sched = sorted((int(c["schedule"].split()[0]), int(c["schedule"].split()[1])) for c in crons)
        self.assertEqual(sched, sorted((M.CRON_MINUTE, h) for h in M.CRON_HOURS_UTC))

    def test_scheduled_count_forward_window(self):
        from bot import metrics as M
        start, end = M.forward_window()
        self.assertEqual(len(M.scheduled_cron_times(start, end)), 80)   # 10 hari x 8


class Reconciliation(unittest.TestCase):
    def test_dashboard_matches_recompute_offline(self):
        html = os.path.join(ROOT, "dashboard.html")
        if not (os.path.exists(html) and os.path.exists(os.path.join(ROOT, "data", "candles", "BTCIDR_1D.json"))):
            self.skipTest("dashboard/candle tidak ada")
        import hitung_ulang as H
        from bot import report
        from bot.timeutil import parse_iso
        D_html = report.extract_data(open(html, encoding="utf-8").read())
        D = H.canon(H.compute(True, parse_iso(D_html["generated_for_now"])))
        for k in ("forward", "backtest_same_window", "uptime", "signal_match", "gap"):
            self.assertEqual(json.dumps(D[k], sort_keys=True, default=str),
                             json.dumps(D_html[k], sort_keys=True, default=str), k)


if __name__ == "__main__":
    unittest.main()
