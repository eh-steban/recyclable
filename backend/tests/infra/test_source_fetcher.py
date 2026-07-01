"""Tests for HttpSourceFetcher -- SSRF controls (INV-LLM-006).

Verifies:
- Private/loopback/link-local IP addresses are rejected before body is read
- Cloud metadata addresses (169.254.169.254) are rejected
- Non-http/https schemes are rejected
- Over-cap bodies are rejected (FETCH_MAX_BYTES)
- Idempotent: same URL returns byte-identical source_text
"""

import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.domain.ingestion.source_fetcher import FetchError, SourceFetchResult
from src.infra.external.source_fetcher import (
    FETCH_MAX_BYTES,
    FETCH_TIMEOUT_S,
    HttpSourceFetcher,
)


class TestSchemeValidation:
    def test_ftp_scheme_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with pytest.raises(FetchError, match="scheme"):
            fetcher.fetch("ftp://example.com/page")

    def test_file_scheme_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with pytest.raises(FetchError, match="scheme"):
            fetcher.fetch("file:///etc/passwd")

    def test_javascript_scheme_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with pytest.raises(FetchError, match="scheme"):
            fetcher.fetch("javascript:alert(1)")

    def test_https_scheme_accepted(self) -> None:
        fetcher = HttpSourceFetcher()
        body = b"<html>Glass bottles are accepted curbside.</html>"
        with _mock_safe_fetch("https://example.com/recycling", body):
            result = fetcher.fetch("https://example.com/recycling")
        assert isinstance(result, SourceFetchResult)

    def test_http_scheme_accepted(self) -> None:
        fetcher = HttpSourceFetcher()
        body = b"<html>Recycle cardboard.</html>"
        with _mock_safe_fetch("http://example.com/recycling", body):
            result = fetcher.fetch("http://example.com/recycling")
        assert isinstance(result, SourceFetchResult)


class TestSSRFDenyList:
    def test_loopback_ipv4_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns("127.0.0.1"),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://localhost/admin")

    def test_private_rfc1918_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns("10.0.0.1"),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://internal.corp/api")

    def test_cloud_metadata_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns("169.254.169.254"),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://169.254.169.254/latest/meta-data/")

    def test_link_local_ipv6_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns_ipv6("fe80::1"),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://[fe80::1]/")

    def test_ipv6_loopback_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns_ipv6("::1"),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://[::1]/")


class TestBodySizeCap:
    def test_body_over_cap_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        oversized = b"x" * (FETCH_MAX_BYTES + 1)
        with (
            _mock_safe_fetch("https://example.com/big", oversized),
            pytest.raises(FetchError, match="too large"),
        ):
            fetcher.fetch("https://example.com/big")

    def test_body_at_cap_accepted(self) -> None:
        fetcher = HttpSourceFetcher()
        body = b"A" * FETCH_MAX_BYTES
        with _mock_safe_fetch("https://example.com/ok", body):
            result = fetcher.fetch("https://example.com/ok")
        assert result.source_text is not None


class TestSourceTextHash:
    def test_hash_is_sha256_of_source_text(self) -> None:
        fetcher = HttpSourceFetcher()
        body = b"<html>Recycle glass!</html>"
        with _mock_safe_fetch("https://example.com/r", body):
            result = fetcher.fetch("https://example.com/r")
        expected = hashlib.sha256(result.source_text.encode()).hexdigest()
        assert result.source_text_hash == expected

    def test_idempotent_same_url_same_hash(self) -> None:
        fetcher = HttpSourceFetcher()
        body = b"<html>Stable content</html>"
        with _mock_safe_fetch("https://example.com/stable", body):
            r1 = fetcher.fetch("https://example.com/stable")
        with _mock_safe_fetch("https://example.com/stable", body):
            r2 = fetcher.fetch("https://example.com/stable")
        assert r1.source_text_hash == r2.source_text_hash


class TestConstants:
    def test_fetch_max_bytes_is_5mb(self) -> None:
        assert FETCH_MAX_BYTES == 5 * 1024 * 1024

    def test_fetch_timeout_s_is_30(self) -> None:
        assert FETCH_TIMEOUT_S == 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _mock_safe_fetch(url: str, body: bytes) -> Generator[None]:
    """Patch DNS and HTTP so no real network call is made.

    The DNS check sees a public IP; the response body is the given bytes.
    """
    with (
        patch(
            "src.infra.external.source_fetcher._resolve_ip",
            return_value="93.184.216.34",  # example.com -- public
        ),
        patch(
            "src.infra.external.source_fetcher._http_get",
            return_value=body,
        ),
    ):
        yield


@contextmanager
def _mock_dns(ip: str) -> Generator[None]:
    """Patch DNS resolution to return a specific IPv4 address."""
    with patch(
        "src.infra.external.source_fetcher._resolve_ip",
        return_value=ip,
    ):
        yield


@contextmanager
def _mock_dns_ipv6(ip: str) -> Generator[None]:
    """Patch DNS resolution to return a specific IPv6 address."""
    with patch(
        "src.infra.external.source_fetcher._resolve_ip",
        return_value=ip,
    ):
        yield
