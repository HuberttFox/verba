"""Thin httpx wrapper: JSON calls + SSE streaming, provider-friendly."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import httpx

from verba.config.schema import HttpOptions
from verba.providers.errors import NetworkError, QuotaExceeded


class HttpError(Exception):
    """Non-2xx response. Carries the status code for the UI to display."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class HttpClient:
    """Shared client for all remote providers.

    One instance per app (configured from HttpOptions); providers receive
    it from their factory instead of creating raw httpx clients.
    """

    def __init__(self, options: HttpOptions | None = None) -> None:
        opts = options or HttpOptions()
        self._options = opts
        self._client = httpx.Client(
            timeout=opts.timeout,
            headers={"User-Agent": opts.user_agent},
            follow_redirects=True,
        )

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._send(
            lambda: self._client.post(
                url, json=payload, headers=headers, params=params
            )
        )

    def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._send(
            lambda: self._client.get(url, headers=headers, params=params)
        )

    def stream_sse(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Iterator[str]:
        """Yield SSE ``data:`` lines (for streaming LLM-style providers)."""
        try:
            with self._client.stream(
                "POST" if payload is not None else "GET",
                url,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        yield line[len("data:") :].strip()
        except httpx.HTTPStatusError as exc:
            raise self._map_error(exc) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(str(exc)) from exc

    def close(self) -> None:
        self._client.close()

    def _send(self, request: Callable[[], httpx.Response]) -> dict[str, Any]:
        try:
            response = request()
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._map_error(exc) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(str(exc)) from exc
        data = response.json()
        if not isinstance(data, dict):
            raise HttpError(response.status_code, "response is not a JSON object")
        return data

    @staticmethod
    def _map_error(exc: httpx.HTTPStatusError) -> HttpError | QuotaExceeded:
        status = exc.response.status_code
        if status in (429, 402):
            return QuotaExceeded(f"HTTP {status}")
        return HttpError(status, exc.response.text[:200])
