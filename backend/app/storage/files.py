"""Original uploaded files, stored under `<user_id>/<document_id><ext>`.

"supabase": a private Supabase Storage bucket, reached only with the service-role key from the server.
"local": DOCULENS_DATA_DIR/files on disk (laptop installs and tests).
"""
import logging
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

import httpx

from app import config

log = logging.getLogger(__name__)

_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


def object_key(user_id: str, document_id: str, ext: str) -> str:
    key = f"{user_id}/{document_id}{ext}"
    if not all(_SAFE_PART.match(p) for p in key.split("/")):
        raise ValueError("unsafe storage key")
    return key


class StorageError(RuntimeError):
    pass


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise StorageError("path escapes the storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> Optional[bytes]:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def delete(self, keys: List[str]) -> None:
        for key in keys:
            path = self._path(key)
            if path.exists():
                path.unlink()


class SupabaseStorage:
    def __init__(self, url: str, service_key: str, bucket: str):
        if not url or not service_key:
            raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase storage")
        self.base = f"{url}/storage/v1/object"
        self.bucket = bucket
        self.headers = config.supabase_service_headers()

    def _url(self, key: str) -> str:
        return f"{self.base}/{self.bucket}/{quote(key)}"

    def put(self, key: str, data: bytes, content_type: str) -> None:
        r = httpx.post(self._url(key), content=data, timeout=60,
                       headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"})
        if r.status_code >= 300:
            raise StorageError(f"upload failed ({r.status_code})")

    def get(self, key: str) -> Optional[bytes]:
        r = httpx.get(self._url(key), headers=self.headers, timeout=60)
        if r.status_code in (400, 404):
            return None
        if r.status_code >= 300:
            raise StorageError(f"download failed ({r.status_code})")
        return r.content

    def delete(self, keys: List[str]) -> None:
        if not keys:
            return
        r = httpx.request("DELETE", f"{self.base}/{self.bucket}", json={"prefixes": keys}, headers=self.headers,
                          timeout=60)
        if r.status_code >= 300:
            log.warning("Storage delete returned %s for %d objects", r.status_code, len(keys))


_storage = None


def storage():
    global _storage
    if _storage is None:
        if config.STORAGE_BACKEND == "supabase":
            _storage = SupabaseStorage(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY,
                                       config.SUPABASE_STORAGE_BUCKET)
        else:
            _storage = LocalStorage(config.FILES_DIR)
    return _storage
