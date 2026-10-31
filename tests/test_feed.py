"""HTTP feed transport regression tests. No real network requests."""
from io import BytesIO
import ssl
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from ceetex_feed import (
    HTTP_TIMEOUT_SECONDS, MAX_FEED_BYTES, fetch_http_feed, verified_ssl_context,
)


class Response(BytesIO):
    def __init__(self, body: bytes, headers=None, url="https://example.org/feed"):
        super().__init__(body)
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


def test_conditional_headers_timeout_and_result():
    seen = []

    def opener(request, *, timeout, context):
        seen.append((dict(request.header_items()), timeout, context))
        return Response(b"<rss/>", {"ETag": '"v2"', "Last-Modified": "yesterday"})

    with patch("ceetex_feed.urlopen", opener):
        result = fetch_http_feed("https://example.org/feed", etag='"v1"', last_modified="earlier")
    headers, timeout, context = seen[0]
    assert timeout == HTTP_TIMEOUT_SECONDS
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.get_ca_certs()
    assert headers["If-none-match"] == '"v1"'
    assert headers["If-modified-since"] == "earlier"
    assert result.body == b"<rss/>"
    assert result.etag == '"v2"'
    assert result.last_modified == "yesterday"


def test_http_not_modified_retains_existing_validators():
    error = HTTPError("https://example.org/feed", 304, "Not Modified", {}, None)
    with patch("ceetex_feed.urlopen", side_effect=error):
        result = fetch_http_feed("https://example.org/feed", etag='"v1"')
    assert result.not_modified
    assert result.body is None
    assert result.etag == '"v1"'


@pytest.mark.parametrize("size", [MAX_FEED_BYTES + 1, MAX_FEED_BYTES + 100])
def test_rejects_oversized_feed_even_without_content_length(size):
    with patch("ceetex_feed.urlopen", return_value=Response(b"x" * size)):
        with pytest.raises(ValueError, match="maximum download size"):
            fetch_http_feed("https://example.org/feed")


def test_early_reject_on_content_length():
    with patch("ceetex_feed.urlopen", return_value=Response(b"ok", {"Content-Length": str(MAX_FEED_BYTES + 1)})):
        with pytest.raises(ValueError, match="maximum download size"):
            fetch_http_feed("https://example.org/feed")


def test_rejects_non_http_and_redirected_non_http():
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        fetch_http_feed("file:///etc/passwd")
    with patch("ceetex_feed.urlopen", return_value=Response(b"<rss/>", url="file:///etc/passwd")):
        with pytest.raises(ValueError, match="redirect"):
            fetch_http_feed("https://example.org/feed")


def test_certifi_bundle_loads_even_with_no_platform_root_certs():
    """Reproduce a macOS Python interpreter with an empty default trust store."""
    empty_platform_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert empty_platform_context.get_ca_certs() == []
    with patch("ceetex_feed.ssl.create_default_context", return_value=empty_platform_context):
        result = verified_ssl_context()
    assert result is empty_platform_context
    assert result.verify_mode == ssl.CERT_REQUIRED
    assert result.check_hostname is True
    assert result.get_ca_certs(), "certifi must provide CA roots for HTTPS"


def test_all_requests_keep_strict_tls_verification():
    observed = []
    def opener(request, *, timeout, context):
        observed.append((request.full_url, context.check_hostname, context.verify_mode))
        return Response(b"<rss/>")

    with patch("ceetex_feed.urlopen", opener):
        fetch_http_feed("https://example.org/rss")
        fetch_http_feed("http://example.org/rss")

    assert len(observed) == 2
    assert all(hosts and mode == ssl.CERT_REQUIRED for _, hosts, mode in observed)


def test_ssl_certificate_failure_is_not_silently_ignored():
    from urllib.error import URLError
    failure = URLError(ssl.SSLCertVerificationError("certificate verify failed"))
    with patch("ceetex_feed.urlopen", side_effect=failure):
        with pytest.raises(URLError):
            fetch_http_feed("https://example.org/rss")
