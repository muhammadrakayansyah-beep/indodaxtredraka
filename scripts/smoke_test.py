"""Uji deployment: tanpa secret harus 401, dengan secret harus 200 dan server_time Indodax
terbaca dari fungsi Vercel (bukti uji koneksi). Hasil disimpan ke data/smoke_test.jsonl."""
import json
import os
import time
import urllib.error
import urllib.request

import _lib
from bot.timeutil import iso

_lib.load_dotenv()
url = os.environ["BOT_URL"].rstrip("/") + "/api/tick?src=smoke"


def call(headers):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=280) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


c1, _ = call({})
c2, body = call({"Authorization": "Bearer " + os.environ["CRON_SECRET"]})
res = {"ts": iso(int(time.time())), "no_secret_status": c1, "with_secret_status": c2}
try:
    b = json.loads(body)
    res.update({k: b.get(k) for k in ("status", "server_time", "processed", "api_errors", "duration_s")})
except ValueError:
    res["body"] = body[:300]
_lib.append_jsonl(_lib.p("data", "smoke_test.jsonl"), res)
print(json.dumps(res, indent=2))
assert c1 == 401, "endpoint TIDAK terlindungi"
assert c2 == 200, "panggilan dengan secret gagal"
