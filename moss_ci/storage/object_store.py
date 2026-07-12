from __future__ import annotations
import os
from pathlib import Path


class ObjectStore:
    def __init__(self, backend: str = "local", local_dir: str = "./data/objects", **kwargs):
        self.backend = backend
        if backend == "local":
            self._dir = Path(local_dir)
            self._dir.mkdir(parents=True, exist_ok=True)
        elif backend == "s3":
            self._bucket = kwargs.get("bucket", "moss-ci")
            self._client = None  # Lazy init boto3

    def put(self, key: str, data: bytes):
        if self.backend == "local":
            path = self._dir / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        if self.backend == "local":
            path = self._dir / key
            if path.exists():
                return path.read_bytes()
            return None
