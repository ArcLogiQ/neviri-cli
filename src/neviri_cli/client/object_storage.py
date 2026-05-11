"""Typed wrapper for ``/api/v1/object-storage/*`` (buckets + objects).

The backend uses the OpenStack Swift term ``container``; the CLI exposes the
S3-style term ``bucket``. This client uses ``container`` internally to match
the URL path.

Notes on streaming / resume:

* Upload uses ``httpx``'s multipart ``files=`` so the body streams off disk
  rather than building one giant in-memory string. However, the *backend*
  buffers the upload in memory before forwarding to Swift, so a multi-GB
  upload will hurt the backend. Treat this as best-effort streaming.
* The CLI side supports a per-byte progress callback by wrapping the file
  object in :class:`_CallbackReader`.
* The backend has no Range / multipart-complete / signed-URL flow, so the
  "resumable on retry" line in Story 9's AC is not deliverable without
  backend changes - it's punted to a later story.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from neviri_cli.client.base import BaseClient

PREFIX = "/api/v1/object-storage"

ProgressCallback = Callable[[int], None]


def _as_list(x: Any) -> list[dict[str, Any]]:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class _CallbackReader:
    """File-like wrapper that fires a callback after each ``read`` call.

    Used to provide upload-progress feedback. ``httpx`` reads the file in
    chunks while building the multipart body, so the callback fires N times
    per upload with the chunk size.
    """

    def __init__(self, fp: IO[bytes], on_progress: ProgressCallback) -> None:
        self._fp = fp
        self._on_progress = on_progress

    def read(self, size: int = -1) -> bytes:
        chunk = self._fp.read(size)
        if chunk:
            self._on_progress(len(chunk))
        return chunk

    def __getattr__(self, item: str) -> Any:
        # Forward anything we don't override (close, seek, tell, fileno, ...).
        return getattr(self._fp, item)


class ObjectStorageClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- containers (buckets) ---------------------------------------

    def list_buckets(self) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{PREFIX}/containers"))

    def create_bucket(self, name: str, *, metadata: dict[str, str] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if metadata:
            body["metadata"] = metadata
        return _as_dict(self._base.post(f"{PREFIX}/containers", json=body))

    def get_bucket(self, name: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/containers/{name}"))

    def delete_bucket(self, name: str) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PREFIX}/containers/{name}"))

    # --- objects ----------------------------------------------------

    def list_objects(self, bucket: str, *, prefix: str | None = None) -> list[dict[str, Any]]:
        params = {"prefix": prefix} if prefix else None
        return _as_list(self._base.get(f"{PREFIX}/containers/{bucket}/objects", params=params))

    def upload_object(
        self,
        bucket: str,
        object_name: str,
        file_path: Path,
        *,
        content_type: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """PUT a local file as an object.

        Streams off disk via httpx multipart. ``on_progress`` is called with
        the number of bytes read on each chunk - wire this to a rich.Progress
        bar from the command layer.
        """
        with file_path.open("rb") as raw:
            fp: IO[bytes] = _CallbackReader(raw, on_progress) if on_progress else raw  # type: ignore[assignment]
            files = {
                "file": (
                    file_path.name,
                    fp,
                    content_type or "application/octet-stream",
                )
            }
            return _as_dict(
                self._base.put(
                    f"{PREFIX}/containers/{bucket}/objects/{object_name}",
                    files=files,
                )
            )

    def download_object(
        self,
        bucket: str,
        object_name: str,
        dest: Path,
        *,
        on_progress: ProgressCallback | None = None,
        chunk_size: int = 64 * 1024,
    ) -> int:
        """Stream a backend object to a local file. Returns total bytes written.

        Uses raw httpx streaming so the full body never sits in CLI memory.
        The dest file is opened in write-binary mode and truncated.
        """
        url = f"{PREFIX}/containers/{bucket}/objects/{object_name}"
        # Bypass BaseClient.request because we need streaming response handling.
        # The auth header is already set on the underlying httpx.Client.
        total = 0
        with self._base._client.stream("GET", url) as response:
            if response.status_code >= 400:
                # Read once to surface the error message; reuse BaseClient's mapper.
                response.read()
                self._base._raise_for_response(response)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as out:
                for chunk in response.iter_bytes(chunk_size):
                    if not chunk:
                        continue
                    out.write(chunk)
                    total += len(chunk)
                    if on_progress:
                        on_progress(len(chunk))
        return total

    def delete_object(self, bucket: str, object_name: str) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PREFIX}/containers/{bucket}/objects/{object_name}"))


__all__ = ["PREFIX", "ObjectStorageClient", "ProgressCallback"]
