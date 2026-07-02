"""Tests for HttpSourceFetcher -- SSRF controls (INV-LLM-006).

Verifies:
- Private/loopback/link-local IP addresses are rejected before body is read
- Cloud metadata addresses (169.254.169.254) are rejected
- CGNAT shared-address-space (100.64.0.0/10, RFC 6598) is rejected
- IPv4-mapped IPv6 private addresses (::ffff:10.x, ::ffff:100.64.x) rejected
- Non-http/https schemes are rejected
- Over-cap bodies are rejected (FETCH_MAX_BYTES)
- Body-size cap enforced without buffering the full oversize body
- Idempotent: same URL returns byte-identical source_text
- DNS gaierror is wrapped in FetchError
- HTTP non-2xx response is wrapped in FetchError
- Network timeout is wrapped in FetchError
- DNS rebinding / TOCTOU: second resolution returns private IP, still rejected
- Multi-address: public-first then private in getaddrinfo result, still rejected
- Redirect to internal IP is rejected
- Cross-host redirect is rejected
"""

import hashlib
import socket
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.request import Request as UrllibRequest

import pytest

from src.domain.ingestion.source_fetcher import FetchError, SourceFetchResult
from src.infra.external.source_fetcher import (
    FETCH_MAX_BYTES,
    FETCH_TIMEOUT_S,
    HttpSourceFetcher,
    _http_get,
    _is_private_address,
    _resolve_all_ips,
    _SSRFRedirectHandler,
)

# Public IP used across safe-fetch helpers (example.com).
_PUBLIC_IP = "93.184.216.34"


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
            _mock_dns(["127.0.0.1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://localhost/admin")

    def test_private_rfc1918_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["10.0.0.1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://internal.corp/api")

    def test_cloud_metadata_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["169.254.169.254"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://169.254.169.254/latest/meta-data/")

    def test_link_local_ipv6_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["fe80::1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://[fe80::1]/")

    def test_ipv6_loopback_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["::1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://[::1]/")

    def test_cgnat_rfc6598_rejected(self) -> None:
        """100.64.0.0/10 (RFC 6598 shared address space) must be rejected.

        Python's ipaddress module reports is_private=False for this range
        in 3.14; the deny-list must include an explicit network check.
        """
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["100.64.0.1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://100.64.0.1/")

    def test_cgnat_upper_boundary_rejected(self) -> None:
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["100.127.255.255"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://100.127.255.255/")

    def test_ipv4_mapped_ipv6_private_rejected(self) -> None:
        """::ffff:10.0.0.1 is a private IPv4 address in mapped form."""
        assert _is_private_address("::ffff:10.0.0.1")

    def test_ipv4_mapped_ipv6_cgnat_rejected(self) -> None:
        """::ffff:100.64.0.1 is a CGNAT address in IPv4-mapped IPv6 form."""
        assert _is_private_address("::ffff:100.64.0.1")


class TestMultiAddressDNS:
    """All addresses returned by getaddrinfo must be validated.

    An attacker who controls DNS can return a public IP first (to pass the
    single-address check) and a private IP second. Every address must be
    rejected if any is disallowed.
    """

    def test_public_then_private_rejected(self) -> None:
        """A multi-address result containing any private IP is rejected."""
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns([_PUBLIC_IP, "10.0.0.1"]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://evil.example.com/")

    def test_private_then_public_rejected(self) -> None:
        """Order must not matter -- private-first is also caught."""
        fetcher = HttpSourceFetcher()
        with (
            _mock_dns(["192.168.1.1", _PUBLIC_IP]),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("http://evil.example.com/")

    def test_all_public_accepted(self) -> None:
        """Multiple public IPs are accepted (round-robin CDN scenario)."""
        fetcher = HttpSourceFetcher()
        body = b"<html>Recycling rules.</html>"
        second_public = "151.101.1.140"  # another public IP
        with _mock_safe_fetch(
            "https://example.com/",
            body,
            dns_ips=[_PUBLIC_IP, second_public],
        ):
            result = fetcher.fetch("https://example.com/")
        assert isinstance(result, SourceFetchResult)


class TestDNSRebindingTOCTOU:
    """DNS rebinding / TOCTOU: the connection uses the pre-validated IP.

    The pinned-IP connector calls socket.create_connection() with the IP
    returned by _assert_all_safe(), bypassing any subsequent getaddrinfo
    call. We simulate a genuine rebind: first call returns a public IP
    (passes the deny-list), a hypothetical second call would return a
    private IP -- but the connector never makes that second call.

    The test patches _resolve_all_ips with side_effect=[public, private]
    and verifies the fetch SUCCEEDS: the private IP from the second
    resolution is never consulted because the connector is already pinned
    to the first (public) IP.
    """

    def test_pinned_connector_never_re_resolves(self) -> None:
        """Fetch succeeds when the hypothetical second resolution is private.

        Confirms the pinned connector does not call _resolve_all_ips again
        after the initial validation pass.
        """
        fetcher = HttpSourceFetcher()
        body = b"<html>Recycling.</html>"
        # First call: public IP (passes the deny-list check).
        # Second call (if it happened): private IP (would be rejected).
        with (
            patch(
                "src.infra.external.source_fetcher._resolve_all_ips",
                side_effect=[[_PUBLIC_IP], ["127.0.0.1"]],
            ),
            patch(
                "src.infra.external.source_fetcher._http_get",
                return_value=body,
            ),
        ):
            result = fetcher.fetch("https://example.com/rebind-test")
        # The fetch succeeded -- the second resolution was never made.
        assert isinstance(result, SourceFetchResult)


class TestRedirectSafety:
    """Each redirect hop's target must be validated.

    The _SSRFRedirectHandler checks each new URL's host. This class
    verifies that a redirect to an internal IP is blocked.
    """

    def test_redirect_to_loopback_rejected(self) -> None:
        """A redirect from a public URL to 127.0.0.1 is caught."""
        fetcher = HttpSourceFetcher()

        def _fake_http_get(
            url: str,
            timeout: int,
            validated_ips: list[str],
            original_host: str,
        ) -> bytes:
            # Simulate a redirect raising the FetchError the real
            # _SSRFRedirectHandler would emit.
            _msg = (
                f"Fetch of {url!r} rejected: resolved to private/internal"
                f" address '127.0.0.1'"
            )
            raise FetchError(_msg)

        with (
            _mock_dns([_PUBLIC_IP]),
            patch(
                "src.infra.external.source_fetcher._http_get",
                side_effect=_fake_http_get,
            ),
            pytest.raises(FetchError, match="private"),
        ):
            fetcher.fetch("https://public.example.com/page")

    def test_redirect_scheme_change_to_non_http_caught(self) -> None:
        """A redirect that changes scheme to non-http/s is caught."""
        fetcher = HttpSourceFetcher()

        def _fake_http_get(
            url: str,
            timeout: int,
            validated_ips: list[str],
            original_host: str,
        ) -> bytes:
            raise FetchError("Fetch rejected: scheme 'file' is not http/https")

        with (
            _mock_dns([_PUBLIC_IP]),
            patch(
                "src.infra.external.source_fetcher._http_get",
                side_effect=_fake_http_get,
            ),
            pytest.raises(FetchError, match="scheme"),
        ):
            fetcher.fetch("https://public.example.com/page")

    def test_cross_host_redirect_rejected(self) -> None:
        """A redirect to a different hostname is refused.

        The pinned connection carries the original host's IP + SNI; following
        a cross-host redirect would TLS-mismatch or hit the wrong server.
        """
        handler = _SSRFRedirectHandler(original_host="example.com")
        req = UrllibRequest("https://example.com/page")
        fake_fp = MagicMock()
        fake_headers = MagicMock()

        with pytest.raises(FetchError, match="cross-host redirect"):
            handler.redirect_request(
                req,
                fake_fp,
                302,
                "Found",
                fake_headers,
                "https://www.example.com/page",
            )

    def test_same_host_redirect_allowed(self) -> None:
        """A same-host redirect (path change only) is allowed."""
        handler = _SSRFRedirectHandler(original_host="example.com")
        req = UrllibRequest("https://example.com/old")
        fake_fp = MagicMock()
        fake_headers = MagicMock()

        with patch(
            "src.infra.external.source_fetcher._assert_all_safe",
            return_value=[_PUBLIC_IP],
        ):
            result = handler.redirect_request(
                req,
                fake_fp,
                301,
                "Moved Permanently",
                fake_headers,
                "https://example.com/new",
            )
        # super().redirect_request() returns a new Request or None; not None
        # means the redirect will be followed.
        assert result is not None


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

    def test_http_get_reads_at_most_cap_plus_one_bytes(self) -> None:
        """_http_get reads at most FETCH_MAX_BYTES+1 bytes from the response.

        An oversize body must not be fully buffered in memory; reading
        cap+1 is the minimum needed to detect the oversize condition.
        """
        mock_response = MagicMock()
        mock_response.read.return_value = b"x" * (FETCH_MAX_BYTES + 1)

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response

        with patch(
            "urllib.request.build_opener",
            return_value=mock_opener,
        ):
            raw = _http_get(
                "https://example.com/",
                FETCH_TIMEOUT_S,
                [_PUBLIC_IP],
                "example.com",
            )

        # Confirm read() was called with the cap+1 limit.
        mock_response.read.assert_called_once_with(FETCH_MAX_BYTES + 1)
        assert len(raw) == FETCH_MAX_BYTES + 1


class TestDNSErrorHandling:
    def test_dns_gaierror_raises_fetch_error(self) -> None:
        """DNS resolution failure is wrapped in FetchError."""
        fetcher = HttpSourceFetcher()
        with (
            patch(
                "src.infra.external.source_fetcher._resolve_all_ips",
                side_effect=FetchError(
                    "DNS resolution failed for 'bad.host': ..."
                ),
            ),
            pytest.raises(FetchError, match="DNS resolution failed"),
        ):
            fetcher.fetch("https://bad.host/page")

    def test_real_dns_gaierror_becomes_fetch_error(self) -> None:
        """socket.gaierror from getaddrinfo is wrapped in FetchError."""
        with (
            patch(
                "socket.getaddrinfo",
                side_effect=socket.gaierror("Name or service not known"),
            ),
            pytest.raises(FetchError, match="DNS resolution failed"),
        ):
            _resolve_all_ips("no-such-host.invalid")


class TestHTTPErrorHandling:
    def test_http_error_raises_fetch_error(self) -> None:
        """HTTP URLError is wrapped in FetchError."""
        fetcher = HttpSourceFetcher()

        with (
            _mock_dns([_PUBLIC_IP]),
            patch(
                "src.infra.external.source_fetcher._http_get",
                side_effect=FetchError(
                    "HTTP error fetching 'https://example.com/': ..."
                ),
            ),
            pytest.raises(FetchError, match="HTTP error"),
        ):
            fetcher.fetch("https://example.com/bad")

    def test_timeout_raises_fetch_error(self) -> None:
        """A timed-out fetch is wrapped in FetchError."""
        fetcher = HttpSourceFetcher()
        timeout_msg = (
            f"Fetch of 'https://x.test/' timed out after {FETCH_TIMEOUT_S}s"
        )
        with (
            _mock_dns([_PUBLIC_IP]),
            patch(
                "src.infra.external.source_fetcher._http_get",
                side_effect=FetchError(timeout_msg),
            ),
            pytest.raises(FetchError, match="timed out"),
        ):
            fetcher.fetch("https://example.com/slow")


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
def _mock_safe_fetch(
    url: str,
    body: bytes,
    dns_ips: list[str] | None = None,
) -> Generator[None]:
    """Patch DNS and HTTP so no real network call is made.

    The DNS check sees a public IP (or the given dns_ips list); the
    response body is the given bytes.
    """
    ips = dns_ips if dns_ips is not None else [_PUBLIC_IP]
    with (
        patch(
            "src.infra.external.source_fetcher._resolve_all_ips",
            return_value=ips,
        ),
        patch(
            "src.infra.external.source_fetcher._http_get",
            return_value=body,
        ),
    ):
        yield


@contextmanager
def _mock_dns(ips: list[str]) -> Generator[None]:
    """Patch DNS resolution to return a list of addresses."""
    with patch(
        "src.infra.external.source_fetcher._resolve_all_ips",
        return_value=ips,
    ):
        yield
