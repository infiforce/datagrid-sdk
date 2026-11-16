"""Pick public vs internal download URLs returned by the API (no host rewriting)."""

from __future__ import annotations

import socket
import sys
from typing import Literal
from urllib.parse import urlparse

EndpointMode = Literal["auto", "internal", "public"]

_host_reachable: dict[str, bool] = {}


def probe_host(host: str, port: int, timeout: float = 1.5) -> bool:
    """TCP connect probe; result cached per host:port for the process."""
    key = f"{host}:{port}"
    cached = _host_reachable.get(key)
    if cached is not None:
        return cached
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError:
        ok = False
    _host_reachable[key] = ok
    return ok


def clear_probe_cache() -> None:
    _host_reachable.clear()


def pick_download_url(
    public_url: str,
    internal_url: str,
    endpoint: EndpointMode = "auto",
    *,
    probe_timeout: float = 1.5,
    log: bool = True,
) -> str:
    """Choose among API-provided URLs. Never rewrites hosts."""
    public = (public_url or "").strip()
    internal = (internal_url or "").strip()

    if endpoint == "public":
        if not public:
            raise ValueError("public download_url is empty")
        return public

    if endpoint == "internal":
        if internal:
            return internal
        if log:
            print(
                "warning: download_url_internal empty; falling back to public",
                file=sys.stderr,
            )
        if not public:
            raise ValueError("both download_url and download_url_internal are empty")
        return public

    if not internal:
        if not public:
            raise ValueError("both download_url and download_url_internal are empty")
        return public

    parsed = urlparse(internal)
    host = parsed.hostname
    if not host:
        if log:
            print(
                "warning: download_url_internal has no host; using public",
                file=sys.stderr,
            )
        if not public:
            return internal
        return public

    port = parsed.port
    if port is None:
        port = 443 if (parsed.scheme or "https").lower() == "https" else 80

    if probe_host(host, port, timeout=probe_timeout):
        if log:
            print(f"endpoint: using internal ({host})", flush=True)
        return internal

    if log:
        print(
            f"endpoint: internal host {host} unreachable; using public",
            file=sys.stderr,
            flush=True,
        )
    if not public:
        raise ValueError(
            f"internal host {host} unreachable and public download_url is empty"
        )
    return public
