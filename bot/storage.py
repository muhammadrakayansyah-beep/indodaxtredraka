"""Storage persisten: Upstash Redis (REST) di Vercel; file JSON lokal untuk tes.

Env (salah satu pasangan):
  UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN
  KV_REST_API_URL / KV_REST_API_TOKEN   (nama yang dibuat integrasi Vercel Marketplace)
  BLOB_READ_WRITE_TOKEN                  (Vercel Blob; dibuat otomatis saat store dihubungkan ke project)
Tanpa env tersebut dan dengan LOCAL_STORE=path, storage memakai file lokal.
"""
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

from bot import config as C

STREAMS = ["calls", "signals", "orders", "equity_daily", "errors", "events", "snapshots"]


class RedisStore:
    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self.token = token

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.url + path, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=C.HTTP_TIMEOUT_S) as r:
            return json.loads(r.read())

    def cmd(self, *args):
        res = self._post("", [str(a) for a in args])
        if "error" in res:
            raise RuntimeError(res["error"])
        return res.get("result")

    def pipeline(self, cmds):
        if not cmds:
            return []
        res = self._post("/pipeline", [[str(a) for a in c] for c in cmds])
        for r in res:
            if "error" in r:
                raise RuntimeError(r["error"])
        return [r.get("result") for r in res]

    # API tingkat tinggi
    def get(self, key):
        return self.cmd("GET", C.REDIS_PREFIX + key)

    def set(self, key, value):
        return self.cmd("SET", C.REDIS_PREFIX + key, value)

    def acquire_lock(self, owner):
        return self.cmd("SET", C.REDIS_PREFIX + "lock", owner, "NX", "EX", C.LOCK_TTL_S) == "OK"

    def release_lock(self, owner):
        # hapus hanya jika masih milik kita
        script = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end"
        return self.cmd("EVAL", script, 1, C.REDIS_PREFIX + "lock", owner)

    def append_many(self, items):
        """items: list (stream, dict). Satu round-trip."""
        self.pipeline([["RPUSH", C.REDIS_PREFIX + "log:" + s, json.dumps(d, separators=(",", ":"))]
                       for s, d in items])

    def read_stream(self, stream, batch=500):
        key = C.REDIS_PREFIX + "log:" + stream
        n = int(self.cmd("LLEN", key) or 0)
        out = []
        for start in range(0, n, batch):
            out += [json.loads(x) for x in self.cmd("LRANGE", key, start, start + batch - 1)]
        return out


class BlobStore:
    """Vercel Blob (store public, isi log dry run tidak rahasia; tulis butuh token).

    Tata letak:
      kv/<key>.json            state, kill_switch (ditimpa)
      lock.json                lock (dibuat dengan allow-overwrite=0 -> atomik)
      logs/<UTC>-<id>.json     satu berkas per panggilan: [[stream, record], ...] (append-only)
    """
    API = "https://blob.vercel-storage.com"
    VERSION = "7"

    def __init__(self, token):
        self.token = token
        parts = token.split("_")          # vercel_blob_rw_<storeId>_<rand>
        self.store_id = parts[3].lower()
        self.base = f"https://{self.store_id}.public.blob.vercel-storage.com"
        self._cache = None

    def _req(self, method, url, data=None, headers=None):
        h = {"authorization": f"Bearer {self.token}", "x-api-version": self.VERSION}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=C.HTTP_TIMEOUT_S) as r:
            return r.status, r.read()

    def _put(self, path, body, overwrite=True):
        data = body if isinstance(body, bytes) else body.encode()
        _, out = self._req("PUT", f"{self.API}/{path}", data, {
            "x-add-random-suffix": "0", "x-allow-overwrite": "1" if overwrite else "0",
            "x-cache-control-max-age": "60", "x-content-type": "application/json"})
        return json.loads(out)

    def _fetch(self, path):
        # query unik untuk melewati cache CDN
        url = f"{self.base}/{path}?nocache={uuid.uuid4().hex}"
        try:
            with urllib.request.urlopen(url, timeout=C.HTTP_TIMEOUT_S) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def _delete(self, path):
        self._req("POST", f"{self.API}/delete", json.dumps({"urls": [f"{self.base}/{path}"]}).encode(),
                  {"content-type": "application/json"})

    def _list(self, prefix):
        out, cursor = [], None
        while True:
            q = f"?prefix={prefix}&limit=1000" + (f"&cursor={cursor}" if cursor else "")
            _, body = self._req("GET", self.API + q)
            d = json.loads(body)
            out += d.get("blobs", [])
            if not d.get("hasMore"):
                return out
            cursor = d.get("cursor")

    def get(self, key):
        return self._fetch(f"kv/{key}.json")

    def set(self, key, value):
        self._put(f"kv/{key}.json", str(value))

    def acquire_lock(self, owner):
        body = json.dumps({"owner": owner, "ts": int(time.time())})
        for _ in range(2):
            try:
                self._put("lock.json", body, overwrite=False)
                return True
            except urllib.error.HTTPError as e:
                if e.code not in (400, 409):
                    raise
                cur = self._fetch("lock.json")
                try:
                    age = time.time() - json.loads(cur)["ts"] if cur else C.LOCK_TTL_S + 1
                except ValueError:
                    age = C.LOCK_TTL_S + 1
                if age <= C.LOCK_TTL_S:
                    return False
                self._delete("lock.json")      # lock basi (fungsi mati di tengah jalan)
        return False

    def release_lock(self, owner):
        cur = self._fetch("lock.json")
        try:
            if cur and json.loads(cur).get("owner") == owner:
                self._delete("lock.json")
        except ValueError:
            pass

    def append_many(self, items):
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        self._put(f"logs/{stamp}-{uuid.uuid4().hex[:8]}.json",
                  json.dumps([[s, d] for s, d in items], separators=(",", ":")), overwrite=False)
        self._cache = None

    def _load_all(self):
        if self._cache is None:
            blobs = sorted(self._list("logs/"), key=lambda b: b["pathname"])
            with ThreadPoolExecutor(max_workers=16) as ex:
                bodies = list(ex.map(lambda b: self._fetch(b["pathname"]), blobs))
            cache = {s: [] for s in STREAMS}
            for body in bodies:
                for s, d in json.loads(body or "[]"):
                    cache.setdefault(s, []).append(d)
            self._cache = cache
        return self._cache

    def read_stream(self, stream):
        return list(self._load_all().get(stream, []))


class LocalStore:
    """Pengganti Redis berbasis file untuk tes lokal. Bukan untuk produksi."""

    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            with open(path) as f:
                self.db = json.load(f)
        else:
            self.db = {"kv": {}, "log": {}}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.db, f)

    def get(self, key):
        return self.db["kv"].get(key)

    def set(self, key, value):
        self.db["kv"][key] = value
        self._save()

    def acquire_lock(self, owner):
        if self.db["kv"].get("lock"):
            return False
        self.db["kv"]["lock"] = owner
        self._save()
        return True

    def release_lock(self, owner):
        if self.db["kv"].get("lock") == owner:
            del self.db["kv"]["lock"]
            self._save()

    def append_many(self, items):
        for s, d in items:
            self.db["log"].setdefault(s, []).append(d)
        self._save()

    def read_stream(self, stream):
        return list(self.db["log"].get(stream, []))


def from_env():
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    tok = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    if url and tok:
        return RedisStore(url, tok)
    blob = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if blob:
        return BlobStore(blob)
    local = os.environ.get("LOCAL_STORE")
    if local:
        return LocalStore(local)
    raise RuntimeError("Storage belum dikonfigurasi: set BLOB_READ_WRITE_TOKEN atau UPSTASH_REDIS_REST_URL/TOKEN")
