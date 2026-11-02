"""The file store. Local disk is what development and way B use; the S3 branch is what the free deployment uses (D-70).

Nothing else in the suite touches the S3 branch, and on a free host it is the only store there is: the API container keeps no disk.
These tests cover the calls and the client's configuration; `scripts/storage_check.py` is what proves a real bucket answers.
"""
import io
from types import SimpleNamespace

import pytest

from app.clients import storage


def _s(**kw):
    base = dict(storage_backend="s3", s3_bucket="caresaathi", s3_endpoint="https://acct.r2.cloudflarestorage.com",
                s3_region="auto", s3_access_key="key", s3_secret_key="secret", local_storage_dir="")
    base.update(kw)
    return SimpleNamespace(**base)


class Recorder:
    def __init__(self):
        self.calls = []

    def put_object(self, **kw):
        self.calls.append(("put", kw))

    def get_object(self, **kw):
        self.calls.append(("get", kw))
        return {"Body": io.BytesIO(b"a scan of a prescription")}

    def delete_object(self, **kw):
        self.calls.append(("delete", kw))


@pytest.fixture
def s3(monkeypatch):
    import boto3
    built = {}
    rec = Recorder()

    def fake_client(service, **kw):
        built["service"], built["kw"] = service, kw
        return rec
    monkeypatch.setattr(boto3, "client", fake_client)
    monkeypatch.setattr(storage, "get_settings", lambda: _s())
    return storage.get_storage(), built, rec


def test_the_s3_client_is_built_for_the_endpoint_and_region_we_configured(s3):
    _, built, _ = s3
    assert built["service"] == "s3"
    # R2 documents region "auto". Left unset, boto3 guesses us-east-1 and signs for the wrong region.
    assert built["kw"]["region_name"] == "auto"
    assert built["kw"]["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
    assert built["kw"]["aws_access_key_id"] == "key" and built["kw"]["aws_secret_access_key"] == "secret"


def test_write_read_and_delete_go_to_the_right_bucket_and_key(s3):
    store, _, rec = s3
    store.put("documents/abc.jpg", b"bytes", "image/jpeg")
    assert store.get("documents/abc.jpg") == b"a scan of a prescription"
    store.delete("documents/abc.jpg")
    assert [c[0] for c in rec.calls] == ["put", "get", "delete"]
    assert all(c[1]["Bucket"] == "caresaathi" and c[1]["Key"] == "documents/abc.jpg" for c in rec.calls)
    assert rec.calls[0][1]["ContentType"] == "image/jpeg"


def test_local_disk_round_trips_and_forgets(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "get_settings", lambda: _s(storage_backend="local", local_storage_dir=str(tmp_path)))
    store = storage.get_storage()
    store.put("documents/x.txt", b"hello", "text/plain")
    assert store.get("documents/x.txt") == b"hello"
    store.delete("documents/x.txt")
    with pytest.raises(Exception):
        store.get("documents/x.txt")
    store.delete("documents/x.txt")                      # deleting what is gone is not an error
