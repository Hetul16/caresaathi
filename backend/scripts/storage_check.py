"""Writes, reads back and deletes one small object, to prove the file store is really reachable before the app needs it.

Run it from backend/ with the same environment the API will have:

    STORAGE_BACKEND=s3 S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com S3_BUCKET=caresaathi \
    S3_REGION=auto S3_ACCESS_KEY=... S3_SECRET_KEY=... python scripts/storage_check.py

Nothing else in the repository exercises the S3 path, and a bucket that answers "no such bucket" or refuses the signature only shows
up as a failed upload otherwise. The object it writes is deleted again; it holds no patient data.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.clients.storage import get_storage  # noqa: E402
from app.config import get_settings  # noqa: E402

s = get_settings()
key = f"storage-check/{int(time.time())}.txt"
payload = b"CareSaathi storage check. Synthetic. Safe to delete.\n"

print(f"backend={s.storage_backend}" + (f" endpoint={s.s3_endpoint} bucket={s.s3_bucket} region={s.s3_region}"
                                        if s.storage_backend == "s3" else f" dir={s.local_storage_dir}"))
try:
    store = get_storage()
except Exception as e:
    sys.exit(f"FAIL  could not build the client: {type(e).__name__} - {e}")

for step, fn in (("write", lambda: store.put(key, payload, "text/plain")),
                 ("read back", lambda: store.get(key)),
                 ("delete", lambda: store.delete(key))):
    try:
        got = fn()
    except Exception as e:
        sys.exit(f"FAIL  {step}: {type(e).__name__} - {str(e)[:200]}")
    if step == "read back" and got != payload:
        sys.exit(f"FAIL  read back {len(got)} bytes, not the {len(payload)} written")
    print(f"  PASS  {step}")
print(f"\nthe store works: {key} was written, read and removed")
