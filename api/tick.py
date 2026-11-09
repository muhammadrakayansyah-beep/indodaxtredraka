"""POST/GET /api/tick — satu langkah bot. Dilindungi CRON_SECRET."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from http.server import BaseHTTPRequestHandler  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

from bot import engine, storage  # noqa: E402
from bot.auth import authorized  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _run(self):
        if not authorized(self.headers):
            self._send(401, {"error": "unauthorized"})
            return
        q = parse_qs(urlparse(self.path).query)
        src = (q.get("src") or [""])[0][:32]
        ua = (self.headers.get("User-Agent") or "")[:60]
        trigger = src or ("vercel-cron" if "vercel-cron" in ua else ua or "unknown")
        try:
            store = storage.from_env()
        except RuntimeError as e:
            self._send(500, {"error": str(e)})
            return
        call = engine.run_tick(store, trigger=trigger)
        self._send(200 if call.get("status") in ("ok", "skipped_locked") else 500, call)

    def do_GET(self):
        self._run()

    def do_POST(self):
        self._run()

    def _send(self, code, body):
        data = json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
