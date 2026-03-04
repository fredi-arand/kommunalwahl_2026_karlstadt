import urllib.error

import pytest

from election_fetcher.network import NetworkFetchError, fetch_html


class FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_fetch_html_retries_and_then_succeeds():
    events = [
        urllib.error.URLError("temporary outage"),
        urllib.error.URLError("temporary outage"),
        FakeResponse("<html>ok</html>"),
    ]

    def opener(request, timeout):
        event = events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    sleeps = []
    html = fetch_html(
        "https://example.test/election",
        retries=3,
        backoff_factor=0.5,
        opener=opener,
        sleep_fn=sleeps.append,
    )

    assert html == "<html>ok</html>"
    assert sleeps == [0.5, 1.0]


def test_fetch_html_stops_retrying_on_non_retryable_http_error():
    url = "https://example.test/election"
    error = urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    def opener(request, timeout):
        raise error

    sleeps = []
    with pytest.raises(NetworkFetchError):
        fetch_html(url, retries=5, opener=opener, sleep_fn=sleeps.append)

    assert sleeps == []


def test_fetch_html_retries_retryable_http_error_until_exhausted():
    url = "https://example.test/election"
    call_count = 0

    def opener(request, timeout):
        nonlocal call_count
        call_count += 1
        raise urllib.error.HTTPError(
            url, 503, "Service Unavailable", hdrs=None, fp=None
        )

    sleeps = []
    with pytest.raises(NetworkFetchError) as exc_info:
        fetch_html(url, retries=3, opener=opener, sleep_fn=sleeps.append)

    assert call_count == 3
    assert sleeps == [1.0, 2.0]
    assert "after 3 attempt(s)" in str(exc_info.value)
