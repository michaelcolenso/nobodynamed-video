"""Async HTTP client for the Satori sidecar service.

Wraps httpx.AsyncClient with:
- Connect timeout: 2 s
- Read timeout: 10 s
- 3 retries with exponential backoff (1 s, 2 s, 4 s)
- Concurrency semaphore: 8 in-flight requests
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from nobodynamed_video.exceptions import FrameRenderFailed, SatoriUnavailable

log = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 2.0
_READ_TIMEOUT = 10.0
_MAX_RETRIES = 3
_CONCURRENCY = 8
_BACKOFF_BASE = 1.0


class SatoriClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(_CONCURRENCY)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> SatoriClient:
        timeout = httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=5.0, pool=None)
        # This is a loopback-only service; inheriting corporate/SOCKS proxy
        # variables breaks localhost and can route render payloads off-host.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            trust_env=False,
        )
        await self._health_check()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _health_check(self) -> None:
        assert self._client is not None
        try:
            resp = await self._client.get("/health")
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise SatoriUnavailable(
                f"Satori is not reachable at {self._base_url}. "
                "Start it with: cd satori-service && pnpm dev"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SatoriUnavailable(f"Satori /health returned {exc.response.status_code}") from exc

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("SatoriClient must be used as an async context manager")
        return self._client

    async def render(self, template: str, props: dict[str, Any]) -> bytes:
        """POST /render and return PNG bytes. Retries up to _MAX_RETRIES times."""
        payload = {"template": template, "props": props}
        last_exc: Exception | None = None

        async with self._semaphore:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = await self._http.post("/render", json=payload)
                    if resp.status_code == 500:
                        body = resp.text
                        raise FrameRenderFailed(
                            f"Satori /render returned 500 for template={template!r}: {body}"
                        )
                    resp.raise_for_status()
                    return resp.content
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    last_exc = exc
                    if attempt < _MAX_RETRIES:
                        delay = _BACKOFF_BASE * (2**attempt)
                        log.warning(
                            "Satori render attempt %d/%d failed (%s), retrying in %.1fs",
                            attempt + 1,
                            _MAX_RETRIES + 1,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                except FrameRenderFailed:
                    raise
                except httpx.HTTPStatusError as exc:
                    raise FrameRenderFailed(
                        f"Satori /render HTTP {exc.response.status_code} for {template!r}"
                    ) from exc

        raise SatoriUnavailable(
            f"Satori unreachable after {_MAX_RETRIES + 1} attempts"
        ) from last_exc

    async def get_version(self) -> str:
        """Best-effort satori version for the manifest — never fails a render."""
        try:
            resp = await self._http.get("/health")
            resp.raise_for_status()
            return str(resp.json().get("satori", "unknown"))
        except httpx.HTTPError as exc:
            log.warning("Could not fetch satori version for manifest: %r", exc)
            return "unknown"
