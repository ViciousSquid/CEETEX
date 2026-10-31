"""Bounded HTTP transport for RSS/Atom feeds.

This module deliberately performs no Textual UI operations. All network activity
runs in CEETEX's background feed worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import BoundedSemaphore
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_FEED_BYTES = 2 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 10
MAX_CONCURRENT_DOWNLOADS = 3
_DOWNLOAD_SLOTS = BoundedSemaphore(MAX_CONCURRENT_DOWNLOADS)

USER_AGENT = "CEETEX/1.0 (+https://github.com/ViciousSquid/CEETEX)"


@dataclass(frozen=True)
class HTTPFeedResult:
    body: bytes | None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


def fetch_http_feed(
    url: str, *, etag: str | None = None, last_modified: str | None = None,
) -> HTTPFeedResult:
    """Fetch a feed with explicit limits and HTTP conditional revalidation.

    A 304 is only useful if the caller supplied an existing snapshot. The
    transport returns the 304 outcome; the UI decides whether it has data.
    """
    if urlsplit(url).scheme.lower() not in ("http", "https"):
        raise ValueError("Feed URLs must use HTTP or HTTPS")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
        "Accept-Encoding": "identity",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    request = Request(url, headers=headers)

    with _DOWNLOAD_SLOTS:
        try:
            response = urlopen(request, timeout=HTTP_TIMEOUT_SECONDS)
        except HTTPError as exc:
            if exc.code != 304:
                raise
            return HTTPFeedResult(None, exc.headers.get("ETag", etag),
                                  exc.headers.get("Last-Modified", last_modified),
                                  not_modified=True)

        with response:
            if response.geturl() and urlsplit(response.geturl()).scheme.lower() not in ("http", "https"):
                raise ValueError("Feed redirect must use HTTP or HTTPS")
            length = response.headers.get("Content-Length")
            try:
                declared_length = int(length) if length is not None else None
            except (TypeError, ValueError):
                declared_length = None
            if declared_length is not None and declared_length > MAX_FEED_BYTES:
                raise ValueError("Feed exceeds maximum download size")
            body = response.read(MAX_FEED_BYTES + 1)
            if len(body) > MAX_FEED_BYTES:
                raise ValueError("Feed exceeds maximum download size")
            return HTTPFeedResult(body, response.headers.get("ETag"),
                                  response.headers.get("Last-Modified"))
