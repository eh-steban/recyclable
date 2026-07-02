"""HttpSourceFetcher -- SSRF-safe HTTP source fetcher.

INV-LLM-006: every fetch enforces the deny-list before any network I/O and
after each redirect hop. Private, loopback, link-local, cloud-metadata, and
CGNAT addresses are rejected. Non-http/https schemes are rejected immediately.

SSRF hardening implemented here:

1. All-address validation: _resolve_all_ips() returns every address
   getaddrinfo() yields for a host. _assert_all_safe() rejects the request
   if ANY address in the result is disallowed. An attacker who orders a
   public IP first and a private IP second is still caught.

2. CGNAT (RFC 6598) explicit check: 100.64.0.0/10 is not reported as
   is_private by Python's ipaddress module; the deny-list includes an
   explicit network membership check.

3. Pinned-IP connector: after validation, _http_get() connects to the
   first validated IP directly via a custom HTTPConnection subclass that
   overrides connect(), preventing a second getaddrinfo() call inside the
   HTTP client (DNS rebinding / TOCTOU). The Host header and SNI are
   preserved from the original URL so TLS and virtual hosting work.

4. Redirect re-check: _SSRFRedirectHandler validates the redirect target's
   host (all addresses) before following the hop. Cross-host redirects
   are refused to prevent IP/SNI mismatch on the pinned connection.

Module-level constants are named with their derivation (plan § Reference Data
§ Pinned adapter constants):

- FETCH_MAX_BYTES: 5 MB -- design Q2 default; caps body before extraction.
- FETCH_TIMEOUT_S: 30 s -- design Q2 default; per-fetch wall-clock timeout.

The internal helpers (_resolve_all_ips, _http_get) are thin wrappers so
tests can patch them without patching socket / urllib internals.
"""

# pyright: reportAny=false, reportExplicitAny=false

import hashlib
import http.client
import ipaddress
import logging
import socket
import ssl
import urllib.parse
import urllib.request
import uuid
from http.client import HTTPMessage
from typing import IO, Any, Final, final, override
from urllib.error import URLError

from src.domain.ingestion.source_fetcher import FetchError, SourceFetchResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants (plan § Reference Data § Pinned adapter constants)
# ---------------------------------------------------------------------------

# 5 MB -- design Q2 default for single-page extraction budget.
FETCH_MAX_BYTES: Final[int] = 5 * 1024 * 1024

# 30 s -- design Q2 default; keeps a stalled page from blocking the worker.
FETCH_TIMEOUT_S: Final[int] = 30

# RFC 6598 shared address space (CGNAT); not in Python's is_private set.
_CGNAT_NETWORK: Final = ipaddress.ip_network("100.64.0.0/10")


# ---------------------------------------------------------------------------
# IP safety check
# ---------------------------------------------------------------------------


def _resolve_all_ips(host: str) -> list[str]:
    """Resolve host and return ALL addresses getaddrinfo() yields.

    Returns a list of address strings (IPv4 dotted-decimal or IPv6 colon
    notation). Raises FetchError if resolution fails or returns no results.

    Returning all addresses (not just [0]) lets _assert_all_safe() reject
    a host where the attacker orders a public IP first and a private one
    second (Finding 2: incomplete DNS validation).
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError) as exc:
        raise FetchError(f"DNS resolution failed for {host!r}: {exc}") from exc

    if not infos:
        raise FetchError(f"Could not resolve host: {host!r}")

    # getaddrinfo returns (family, type, proto, canonname, sockaddr).
    # sockaddr[0] is the address string for IPv4 and IPv6.
    return [str(info[4][0]) for info in infos]


def _is_private_address(addr_str: str) -> bool:
    """Return True if addr_str is in any denied range.

    Denied ranges:
    - Loopback (127.0.0.0/8, ::1)
    - Private RFC 1918 (10/8, 172.16/12, 192.168/16)
    - Link-local (169.254/16, fe80::/10)
    - Reserved / unspecified
    - CGNAT RFC 6598 (100.64.0.0/10) -- not covered by is_private in 3.14
    - ULA (fc00::/7) -- covered by is_private in 3.14, but made explicit

    IPv4-mapped IPv6 (::ffff:10.x.x.x etc.) is handled by Python 3.14's
    is_private / is_link_local properties which unwrap the mapping.
    """
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        # Unparseable -- cannot verify safety, so reject.
        return True

    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        # Cloud-metadata prefix -- already caught by is_link_local, but kept
        # explicit for defence-in-depth.
        or addr_str.startswith("169.254.")
    ):
        return True

    # CGNAT / shared-address-space RFC 6598: 100.64.0.0/10.
    # Python 3.14 ipaddress reports is_private=False for this range.
    if isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT_NETWORK:
        return True

    # IPv4-mapped IPv6: unwrap and check the embedded IPv4 address.
    # Python 3.14 covers most cases via is_private/is_link_local, but the
    # CGNAT range needs explicit handling on the mapped form too.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        mapped = addr.ipv4_mapped
        if mapped in _CGNAT_NETWORK:
            return True

    return False


def _assert_all_safe(host: str, url: str) -> list[str]:
    """Resolve host and reject if ANY returned IP is in the deny-list.

    Returns the validated list of IPs so the caller can pin the connection.

    Fixes Finding 1 (TOCTOU) and Finding 2 (first-address-only): the
    caller uses the returned list to open the socket directly, and every
    address is checked before any connection is made.
    """
    ips = _resolve_all_ips(host)
    for ip in ips:
        if _is_private_address(ip):
            msg = (
                f"Fetch of {url!r} rejected: resolved to private/internal"
                f" address {ip!r}"
            )
            raise FetchError(msg)
    return ips


# ---------------------------------------------------------------------------
# Pinned-IP HTTP connection (DNS rebinding / TOCTOU fix)
# ---------------------------------------------------------------------------


@final
class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection that connects to a pre-validated IP.

    Overrides connect() to call socket.create_connection() with the pinned
    IP address instead of re-resolving self.host. The Host header used in
    the HTTP request is the original hostname, preserved by urllib, so
    virtual hosting and TLS SNI are not affected.

    This closes the TOCTOU window: urllib's internal getaddrinfo() call is
    bypassed; the socket connects to the IP we already validated.
    """

    _pinned_ip: str

    def __init__(self, host: str, pinned_ip: str, **kwargs: Any) -> None:
        super().__init__(host, **kwargs)
        self._pinned_ip = pinned_ip

    @override
    def connect(self) -> None:
        self.sock: socket.socket = socket.create_connection(
            (self._pinned_ip, self.port or 80),
            timeout=self.timeout,
        )


@final
class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection that connects to a pre-validated IP with SNI.

    The TLS handshake uses the original hostname for SNI so certificates
    that carry the hostname (not the IP) are validated correctly.
    """

    _pinned_ip: str
    _original_host: str

    def __init__(
        self,
        host: str,
        pinned_ip: str,
        original_host: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(host, **kwargs)
        self._pinned_ip = pinned_ip
        self._original_host = original_host

    @override
    def connect(self) -> None:
        plain_sock = socket.create_connection(
            (self._pinned_ip, self.port or 443),
            timeout=self.timeout,
        )
        ctx = ssl.create_default_context()
        self.sock: ssl.SSLSocket = ctx.wrap_socket(
            plain_sock,
            server_hostname=self._original_host,
        )


# ---------------------------------------------------------------------------
# Custom urllib handlers (use pinned connections + SSRF redirect guard)
# ---------------------------------------------------------------------------


class _SSRFHTTPHandler(urllib.request.HTTPHandler):
    """HTTP handler that validates all DNS addresses and pins the connection."""

    _validated_ips: list[str]

    def __init__(self, validated_ips: list[str]) -> None:
        super().__init__()
        self._validated_ips = validated_ips

    @override
    def http_open(
        self, req: urllib.request.Request
    ) -> http.client.HTTPResponse:
        pinned = self._validated_ips[0]

        def _make_conn(host: str, **kwargs: Any) -> _PinnedHTTPConnection:
            return _PinnedHTTPConnection(host, pinned_ip=pinned, **kwargs)

        return self.do_open(_make_conn, req)


class _SSRFHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS handler that validates all DNS addresses and pins connections."""

    _validated_ips: list[str]
    _original_host: str

    def __init__(self, validated_ips: list[str], original_host: str) -> None:
        super().__init__()
        self._validated_ips = validated_ips
        self._original_host = original_host

    @override
    def https_open(
        self, req: urllib.request.Request
    ) -> http.client.HTTPResponse:
        pinned = self._validated_ips[0]
        original_host = self._original_host

        def _make_conn(host: str, **kwargs: Any) -> _PinnedHTTPSConnection:
            return _PinnedHTTPSConnection(
                host,
                pinned_ip=pinned,
                original_host=original_host,
                **kwargs,
            )

        return self.do_open(_make_conn, req)


class _SSRFRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-checks ALL resolved addresses on each hop.

    Cross-host redirects (host changes between the original request and
    the redirect target) are refused. A cross-host redirect would require
    rebuilding the pinned connection with the new host's validated IPs;
    doing so inside the handler is error-prone and unnecessary for the
    single-page ingest use-case. Raise FetchError so the caller can retry
    with the canonical URL if needed.
    """

    _original_host: str

    def __init__(self, original_host: str) -> None:
        super().__init__()
        self._original_host = original_host

    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        parsed = urllib.parse.urlparse(newurl)

        # Reject non-http/https redirect targets before DNS.
        if parsed.scheme not in ("http", "https"):
            _msg = (
                f"Fetch rejected: redirect to scheme"
                f" {parsed.scheme!r} is not http/https"
            )
            raise FetchError(_msg)

        new_host = parsed.hostname or ""

        # Reject cross-host redirects: the pinned connection carries the
        # original host's IP and SNI; a different host would TLS-mismatch or
        # hit the wrong server.
        if new_host and new_host != self._original_host:
            msg = (
                f"Fetch of {req.full_url!r} rejected: cross-host redirect"
                f" to {newurl!r} (original host {self._original_host!r},"
                f" redirect host {new_host!r})"
            )
            raise FetchError(msg)

        if new_host:
            # Validate every address the redirect target resolves to.
            _ = _assert_all_safe(new_host, newurl)

        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ---------------------------------------------------------------------------
# HTTP GET helper (patchable in tests)
# ---------------------------------------------------------------------------


def _http_get(
    url: str,
    timeout: int,
    validated_ips: list[str],
    original_host: str,
) -> bytes:
    """Fetch url and return raw response bytes using pinned IP connections.

    validated_ips: all IPs returned by _resolve_all_ips() for the original
                   host; the connection is pinned to validated_ips[0].
    original_host: hostname string for TLS SNI and Host header.

    Follows redirects; each redirect hop's target is re-validated by
    _SSRFRedirectHandler. Raises FetchError on HTTP errors or timeouts.
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme

    if scheme == "https":
        scheme_handler: urllib.request.BaseHandler = _SSRFHTTPSHandler(
            validated_ips, original_host
        )
    else:
        scheme_handler = _SSRFHTTPHandler(validated_ips)

    opener = urllib.request.build_opener(
        _SSRFRedirectHandler(original_host),
        scheme_handler,
    )
    try:
        response = opener.open(url, timeout=timeout)
        # Read at most cap+1 bytes; checking length after avoids buffering
        # the full body of an oversize response (S-2 fix).
        return response.read(FETCH_MAX_BYTES + 1)
    except URLError as exc:
        if "timed out" in str(exc).lower():
            raise FetchError(
                f"Fetch of {url!r} timed out after {timeout}s"
            ) from exc
        raise FetchError(f"HTTP error fetching {url!r}: {exc}") from exc
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"Unexpected error fetching {url!r}: {exc}") from exc


# ---------------------------------------------------------------------------
# HttpSourceFetcher
# ---------------------------------------------------------------------------


class HttpSourceFetcher:
    """SSRF-safe HTTP source fetcher implementing the SourceFetcher port.

    Enforces INV-LLM-006 before any network I/O:
    1. Rejects non-http/https schemes.
    2. Resolves ALL addresses for the host and rejects if any is denied.
    3. Connects to the first validated IP directly (no second resolution).
    4. Re-checks ALL addresses on every same-host redirect; cross-host
       redirects are refused.
    5. Reads at most FETCH_MAX_BYTES+1 bytes, then rejects if oversized
       (prevents full-body buffering of malicious oversize responses).
    6. Applies FETCH_TIMEOUT_S wall-clock timeout.

    Idempotent: re-fetching an unchanged URL produces byte-identical
    source_text (the same bytes produce the same hash).
    """

    def fetch(
        self,
        url: str,
        *,
        authority_level: int = 3,
    ) -> SourceFetchResult:
        """Fetch url and return a SourceFetchResult.

        Raises FetchError on any denied URL, oversized body, or timeout.
        """
        parsed = urllib.parse.urlparse(url)

        # 1. Scheme check (before DNS; no network touch on rejection).
        if parsed.scheme not in ("http", "https"):
            raise FetchError(
                f"Fetch rejected: scheme {parsed.scheme!r} is not http/https"
            )

        host = parsed.hostname or ""
        original_host = host

        # 2. Resolve all addresses and validate every one (Findings 1 + 2).
        #    Returns the validated list for connection pinning.
        validated_ips = _assert_all_safe(host, url)

        _log_msg = (
            "fetch_source: fetching url=%r authority_level=%d"
            " timeout=%ds max_bytes=%d"
        )
        logger.info(
            _log_msg, url, authority_level, FETCH_TIMEOUT_S, FETCH_MAX_BYTES
        )

        # 3. Fetch using pinned IP (no second DNS lookup).
        raw = _http_get(url, FETCH_TIMEOUT_S, validated_ips, original_host)

        # 5. Body size cap (after fetch, before decode).
        if len(raw) > FETCH_MAX_BYTES:
            msg = (
                f"Fetch of {url!r} rejected: response body"
                f" {len(raw)} bytes exceeds cap {FETCH_MAX_BYTES} (too large)"
            )
            raise FetchError(msg)

        # Decode as UTF-8 with replacement for robustness on messy pages.
        source_text = raw.decode("utf-8", errors="replace")
        source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()

        logger.info(
            "fetch_source: completed url=%r bytes=%d hash=%s",
            url,
            len(raw),
            source_text_hash[:16],
        )

        return SourceFetchResult(
            id=uuid.uuid4(),
            url=url,
            source_text=source_text,
            source_text_hash=source_text_hash,
            authority_level=authority_level,
            content_type="text/html",
        )
