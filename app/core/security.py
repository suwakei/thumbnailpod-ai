from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_api_key_header = APIKeyHeader(name="X-Internal-Secret", auto_error=False)


async def verify_internal_secret(api_key: str = Security(_api_key_header)) -> None:
    """Verify that the request comes from the Go API (VPC internal shared secret)."""
    if api_key != settings.internal_api_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _allowed_host_suffixes() -> tuple[str, ...]:
    raw = settings.allowed_image_host_suffixes or ""
    return tuple(s.strip().lower().lstrip(".") for s in raw.split(",") if s.strip())


def validate_image_url(url: str) -> None:
    """Reject non-https URLs and hosts outside the configured allowlist.

    Guards against SSRF into the VPC (RDS, ElastiCache, instance metadata)
    when the URL originates from user input relayed by the Go API.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"url scheme must be https: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url has no host")
    suffixes = _allowed_host_suffixes()
    if not any(host == s or host.endswith("." + s) for s in suffixes):
        raise ValueError(f"url host not in allowlist: {host}")


async def fetch_remote_image_bytes(url: str, timeout: float = 30.0) -> bytes:
    """Download an image URL with SSRF allowlisting and size capping.

    - Validates scheme and host against the allowlist
    - Disables redirects (no jump to internal hosts)
    - Rejects responses exceeding settings.max_image_download_bytes
    """
    validate_image_url(url)
    max_bytes = settings.max_image_download_bytes
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            cl = resp.headers.get("content-length")
            if cl is not None:
                try:
                    if int(cl) > max_bytes:
                        raise ValueError(f"image too large: content-length {cl}")
                except ValueError:
                    pass
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise ValueError(
                        f"image too large: exceeded {max_bytes} bytes"
                    )
            return bytes(buf)
