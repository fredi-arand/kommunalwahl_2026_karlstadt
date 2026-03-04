from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable

DEFAULT_USER_AGENT = "Mozilla/5.0"
RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class NetworkFetchError(RuntimeError):
    def __init__(self, url: str, cause: BaseException, attempts: int):
        self.url = url
        self.cause = cause
        self.attempts = attempts
        super().__init__(f"Failed to fetch {url} after {attempts} attempt(s): {cause}")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in RETRYABLE_HTTP_STATUS_CODES
    return isinstance(
        exc, (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError)
    )


def fetch_html(
    url: str,
    *,
    timeout: float = 15.0,
    retries: int = 4,
    backoff_factor: float = 1.0,
    opener: Callable[..., object] = urllib.request.urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            with opener(request, timeout=timeout) as response:
                body = response.read()
            if isinstance(body, bytes):
                return body.decode("utf-8")
            return str(body)
        except BaseException as exc:
            last_error = exc
            if attempt >= retries or not _should_retry(exc):
                break
            delay = backoff_factor * (2 ** (attempt - 1))
            sleep_fn(delay)

    if last_error is None:
        last_error = RuntimeError("unknown network failure")
    raise NetworkFetchError(url, last_error, retries) from last_error
