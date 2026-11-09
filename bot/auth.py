import hmac
import os


def authorized(headers):
    """Endpoint dilindungi CRON_SECRET. Vercel Cron mengirim 'Authorization: Bearer <CRON_SECRET>'
    otomatis; GitHub Actions mengirim header yang sama dari repository secret."""
    secret = os.environ.get("CRON_SECRET", "")
    if len(secret) < 16:          # fail closed bila secret belum diset / terlalu pendek
        return False
    got = headers.get("Authorization", "") or ""
    return hmac.compare_digest(got.encode(), f"Bearer {secret}".encode())
