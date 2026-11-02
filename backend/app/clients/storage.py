"""Object storage (D-05). The database keeps keys and SHA-256 hashes only.

`local` writes under a gitignored folder for development; `s3` talks to any S3-compatible service
(MinIO, RustFS, a cloud bucket). Same interface, so nothing else changes.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path
from typing import Protocol

from ..config import get_settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def new_key(patient_id: str, kind: str, ext: str) -> str:
    """Random key under a per-patient prefix. The original filename is never part of the key."""
    ext = _SAFE.sub("", ext)[:8] or "bin"
    return f"patients/{patient_id}/{kind}/{secrets.token_hex(16)}.{ext}"


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("key escapes storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self) -> None:
        import boto3
        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client("s3", endpoint_url=s.s3_endpoint, region_name=s.s3_region,
                                   aws_access_key_id=s.s3_access_key, aws_secret_access_key=s.s3_secret_key)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage() -> Storage:
    s = get_settings()
    return S3Storage() if s.storage_backend == "s3" else LocalStorage(s.local_storage_dir)


# File type is decided by signature, never by the client's header (docs/15-api-spec.md section 1).
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


def sniff_mime(data: bytes) -> str | None:
    for sig, mime in _SIGNATURES:
        if data.startswith(sig):
            return mime
    return None
