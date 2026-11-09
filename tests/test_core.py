import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import config as C  # noqa: E402
from bot import engine, execution as X, indodax as API, strategy as S, storage  # noqa: E402
from bot.auth import authorized  # noqa: E402
from bot.timeutil import wib_day  # noqa: E402

DAY = 86400


def mk(closes, t0=1_700_000_000 // DAY * DAY):
    return [{"Time": t0 + i * DAY, "Open": c, "High": c, "Low": c, "Close": c, "Volume": 1.0}
            for i, c in enumerate(closes)]


class Strategy(unittest.TestCase):
    def test_rsi_all_up_is_100(self):
        self.assertEqual(S.rsi_wilder([1, 2, 3, 4, 5, 6], 4), 100.0)

    def test_rsi_known(self):
        # perubahan: +1,-1,+1,-1 -> avg_g=avg_l -> 50
        self.assertAlmostEqual(S.rsi_wilder([10, 11, 10, 11, 10], 4), 50.0)

    def test_entry_signal(self):
        closes = [100 + i * 0.5 for i in range(296)] + [240, 230, 220, 210]
        d = S.evaluate(mk(closes), None)
        self.assertEqual(d["action"], "BUY", d)

    def test_no_entry_below_sma200(self):
        closes = [300 - i * 0.5 for i in range(300)]
        self.assertEqual(S.evaluate(mk(closes), None)["action"], "HOLD")

    def test_take_profit_uses_next_open(self):
        cs = mk([100 + i * 0.1 for i in range(300)])
        sig_t = cs[-5]["Time"]
        cs[-4]["Open"] = 50.0   # ref = Open candle setelah candle sinyal
        d = S.evaluate(cs, {"signal_time": sig_t, "ref_price": None})
        self.assertEqual(d["ref_price"], 50.0)
        self.assertEqual(d["action"], "SELL")
        self.assertEqual(d["reason"], "take_profit")

    def test_time_stop(self):
        cs = mk([100.0] * 300)
        d = S.evaluate(cs, {"signal_time": cs[-1]["Time"] - 40 * DAY, "ref_price": 1000.0})
        self.assertEqual((d["action"], d["reason"]), ("SELL", "time_stop"))

    def test_window_length_enforced(self):
        with self.assertRaises(ValueError):
            S.evaluate(mk([1.0] * 10), None)


class Data(unittest.TestCase):
    def test_closed_only_drops_running_bar(self):
        cs = mk([1, 2, 3])
        now = cs[-1]["Time"] + 100  # bar terakhir masih berjalan
        self.assertEqual(len(API.closed_only(cs, now, DAY)), 2)

    def test_wib_day_boundary(self):
        # 16:59:59 UTC = 23:59:59 WIB; 17:00 UTC = 00:00 WIB hari berikutnya
        self.assertEqual(wib_day(1794157199), "2026-11-08")
        self.assertEqual(wib_day(1794157200), "2026-11-09")


class Exec(unittest.TestCase):
    def test_sweep_buy_multi_level(self):
        f = X.sweep_buy_idr([[100.0, 1.0], [110.0, 10.0]], 210.0)
        self.assertAlmostEqual(f["qty"], 2.0)
        self.assertAlmostEqual(f["vwap"], 105.0)

    def test_sweep_sell_partial(self):
        f = X.sweep_sell_qty([[100.0, 1.0], [90.0, 0.5]], 2.0)
        self.assertAlmostEqual(f["qty"], 1.5)
        self.assertAlmostEqual(f["unfilled_qty"], 0.5)


class Auth(unittest.TestCase):
    def test_auth(self):
        with mock.patch.dict(os.environ, {"CRON_SECRET": "x" * 32}):
            self.assertTrue(authorized({"Authorization": "Bearer " + "x" * 32}))
            self.assertFalse(authorized({"Authorization": "Bearer nope"}))
            self.assertFalse(authorized({}))
        with mock.patch.dict(os.environ, {"CRON_SECRET": ""}):
            self.assertFalse(authorized({"Authorization": "Bearer "}))


class EngineIdempotency(unittest.TestCase):
    """Bot dipanggil dua kali untuk candle yang sama -> beli hanya sekali."""

    def setUp(self):
        closes = [100 + i * 0.5 for i in range(296)] + [240, 230, 220, 210]
        t0 = 1_790_000_000 // DAY * DAY
        self.cs = mk(closes + [999], t0)   # bar terakhir = masih berjalan
        self.now = self.cs[-1]["Time"] + 900
        self.tmp = tempfile.mkdtemp()

    def _patches(self):
        book = {"bids": [[209.0, 1e6]], "asks": [[210.0, 1e6]]}
        return [mock.patch.object(API, "server_time", return_value=self.now),
                mock.patch.object(API, "depth", return_value=book),
                mock.patch.object(API, "history", return_value=list(self.cs))]

    def test_twice_same_candle(self):
        st = storage.LocalStore(os.path.join(self.tmp, "db.json"))
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            c1 = engine.run_tick(st, "test")
            c2 = engine.run_tick(st, "test")
        finally:
            for p in ps:
                p.stop()
        buys = [o for o in st.read_stream("orders") if o["side"] == "BUY"]
        self.assertEqual(c1["status"], "ok", c1)
        self.assertEqual(len(buys), len(C.UNIVERSE))       # satu per pair, bukan dua
        self.assertTrue(all(v.startswith("dup:") for v in c2["processed"].values()), c2)
        for o in buys:   # fill di ask, bukan mid/close
            self.assertAlmostEqual(o["avg_fill"], 210.0)
            self.assertLessEqual(o["notional"] + o["fee"], C.MAX_POSITION_FRACTION * C.INITIAL_CAPITAL_IDR + 1e-6)

    def test_kill_switch_blocks_entry(self):
        st = storage.LocalStore(os.path.join(self.tmp, "db2.json"))
        st.set("kill_switch", "1")
        ps = self._patches()
        for p in ps:
            p.start()
        try:
            engine.run_tick(st, "test")
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(st.read_stream("orders"), [])
        types = [e["type"] for e in st.read_stream("events")]
        self.assertIn("kill_switch_on", types)
        self.assertIn("entry_blocked", types)

    def test_lock_prevents_concurrent(self):
        st = storage.LocalStore(os.path.join(self.tmp, "db3.json"))
        st.acquire_lock("other")
        c = engine.run_tick(st, "test")
        self.assertEqual(c["status"], "skipped_locked")

    def test_retry_bounded(self):
        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            raise OSError("timeout")
        errs = []
        with mock.patch("urllib.request.urlopen", side_effect=boom), mock.patch("time.sleep"):
            with self.assertRaises(API.ApiError):
                API.get_json("/api/server_time", errs)
        self.assertEqual(calls["n"], C.HTTP_MAX_RETRIES)
        self.assertEqual(len(errs), C.HTTP_MAX_RETRIES)


if __name__ == "__main__":
    unittest.main()
