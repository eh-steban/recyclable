"""HttpSourceFetcher -- SSRF-safe HTTP source fetcher.

INV-LLM-006: every fetch enforces the deny-list before any network I/O and
after each redirect hop. Private, loopback, link-local, and cloud-metadata
addresses are rejected. Non-http/https schemes are rejected immediately.

Module-level constants are named with their derivation (plan § Reference Data
§ Pinned adapter constants):

- FETCH_MAX_BYTES: 5 MB -- design Q2 default; caps body before extraction.
- FETCH_TIMEOUT_S: 30 s -- design Q2 default; per-fetch wall-clock timeout.

The two internal helpers (_resolve_ip, _http_get) are thin wrappers so tests
can patch them without patching urllib internals.
"""

# pyright: reportAny=false, reportExplicitAny=false

import hashlib
import ipaddress
import logging
import socket
import urllib.parse
import urllib.request
import uuid
from http.client import HTTPMessage
from typing import IO, Final, override
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


# ---------------------------------------------------------------------------
# IP safety check
# ---------------------------------------------------------------------------


def _resolve_ip(host: str) -> str:
    """Resolve host to its first address string (IPv4 or IPv6)."""
    infos = socket.getaddrinfo(host, None)
    if not infos:
        raise FetchError(f"Could not resolve host: {host!r}")
    # getaddrinfo returns (family, type, proto, canonname, sockaddr);
    # sockaddr[0] is the address string for both IPv4 and IPv6.
    addr = infos[0][4][0]
    return str(addr)


def _is_private_address(addr_str: str) -> bool:
    """Return True if addr_str is private, loopback, link-local, or
    a cloud-metadata address."""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        # Unparseable -- cannot verify safety, so reject.
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        # AWS/GCP/Azure instance metadata (link-local; made explicit).
        or addr_str.startswith("169.254.")
    )


def _assert_safe_host(host: str, url: str) -> None:
    """Resolve host and reject if the IP is in the deny-list.

    Raises FetchError with reason 'private' on any denied address.
    """
    try:
        ip = _resolve_ip(host)
    except (socket.gaierror, OSError) as exc:
        raise FetchError(f"DNS resolution failed for {host!r}: {exc}") from exc

    if _is_private_address(ip):
        msg = (
            f"Fetch of {url!r} rejected: resolved to private/internal"
            f" address {ip!r}"
        )
        raise FetchError(msg)


# ---------------------------------------------------------------------------
# HTTP GET helper (patchable in tests)
# ---------------------------------------------------------------------------


def _http_get(url: str, timeout: int) -> bytes:
    """Fetch url and return raw response bytes.

    Follows up to 5 redirects. Each redirect hop's resolved IP is checked
    against the deny-list before the next request is issued.

    Raises FetchError on HTTP errors, timeouts, or denied redirect targets.
    """
    opener = urllib.request.build_opener(
        _SSRFRedirectHandler(), urllib.request.HTTPSHandler()
    )
    try:
        response = opener.open(url, timeout=timeout)
        return response.read()
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


class _SSRFRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-checks the deny-list on each hop."""

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
        host = parsed.hostname or ""
        if host:
            _assert_safe_host(host, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ---------------------------------------------------------------------------
# HttpSourceFetcher
# ---------------------------------------------------------------------------


class HttpSourceFetcher:
    """SSRF-safe HTTP source fetcher implementing the SourceFetcher port.

    Enforces INV-LLM-006 before any network I/O:
    1. Rejects non-http/https schemes.
    2. Resolves the host and rejects private/loopback/link-local/metadata IPs.
    3. Re-checks on every redirect hop via _SSRFRedirectHandler.
    4. Rejects bodies larger than FETCH_MAX_BYTES.
    5. Applies FETCH_TIMEOUT_S wall-clock timeout.

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

        # 2. Pre-fetch IP deny-list check.
        _assert_safe_host(host, url)

        _log_msg = (
            "fetch_source: fetching url=%r authority_level=%d"
            " timeout=%ds max_bytes=%d"
        )
        logger.info(
            _log_msg, url, authority_level, FETCH_TIMEOUT_S, FETCH_MAX_BYTES
        )

        raw = _http_get(url, FETCH_TIMEOUT_S)

        # 4. Body size cap.
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
