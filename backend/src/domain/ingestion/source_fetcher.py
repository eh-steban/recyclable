"""SourceFetcher port and supporting types.

INV-LLM-006: the fetcher is target-restricted. The concrete implementation
enforces SSRF controls; this file declares the domain-facing contract.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol


class FetchError(Exception):
    """Raised by SourceFetcher when a fetch cannot be completed safely.

    Covers: scheme rejection, private-IP / SSRF deny-list, body-size cap
    exceeded, timeout exceeded, and HTTP-level errors.
    """


@dataclass(frozen=True, slots=True)
class SourceFetchResult:
    """Fetched source document payload.

    Fields:
        id: application-generated UUID (minted before the fetch).
        url: the canonical URL that was fetched.
        source_text: normalized extracted text.
        source_text_hash: sha256 hex of source_text for change detection.
        authority_level: caller-supplied authority tier (1=municipal...6=blog).
        content_type: HTTP Content-Type of the response.
    """

    id: uuid.UUID
    url: str
    source_text: str
    source_text_hash: str
    authority_level: int
    content_type: str


class SourceFetcher(Protocol):
    """Port for fetching source documents from external URLs.

    Implementations must enforce INV-LLM-006 (SSRF controls) before any
    network request and after every redirect hop:
    1. Scheme must be http or https.
    2. Resolved IP must not be private, loopback, link-local, or cloud-metadata.
    3. Re-check the resolved IP after each redirect hop.
    4. Truncate/reject bodies over FETCH_MAX_BYTES.
    5. Apply a per-fetch wall-clock timeout of FETCH_TIMEOUT_S.
    """

    def fetch(
        self,
        url: str,
        *,
        authority_level: int = 3,
    ) -> SourceFetchResult: ...
