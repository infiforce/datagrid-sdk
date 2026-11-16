"""Local file integrity helpers (MD5)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def normalize_checksum_algo(algo: str | None) -> str:
    return (algo or "").strip().lower()


def is_md5_algo(algo: str | None) -> bool:
    """Treat empty algo as md5 when a 32-hex checksum is provided by the platform."""
    a = normalize_checksum_algo(algo)
    return a in ("", "md5")


def md5_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def local_matches_checksum(
    path: Path,
    expected: str,
    algo: str | None = None,
) -> bool:
    """Return True when local file exists and MD5 matches expected checksum."""
    expected = (expected or "").strip().lower()
    if not expected or not path.is_file():
        return False
    if not is_md5_algo(algo):
        return False
    return md5_file(path) == expected
