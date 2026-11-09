from datetime import datetime, timezone

from bot import config as C


def iso(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def wib_day(ts):
    """Tanggal WIB (UTC+7); hari berganti 00:00 WIB = 17:00 UTC."""
    return datetime.fromtimestamp(int(ts) + C.WIB_OFFSET_SECONDS, tz=timezone.utc).strftime("%Y-%m-%d")
