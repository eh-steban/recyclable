"""Quote normalization for source-integrity checks.

Both sides of a quote-integrity comparison (``source_quote`` and
``source_documents.source_text``) are normalized with ``_normalize``
before the substring test.  Applying the same transformation to both
sides means cosmetic differences in whitespace or quotation marks never
cause spurious failures.

The five mandatory steps come from the spec
(*Quote-integrity normalization* section):

1. Replace curly single quotes with straight single quotes.
2. Replace curly double quotes with straight double quotes.
3. Replace non-breaking spaces (U+00A0) with regular spaces.
4. Collapse runs of whitespace (including newlines) to a single space.
5. Trim leading and trailing whitespace.
"""

from __future__ import annotations

import re

# Pre-compiled pattern for whitespace collapse (step 4).
_WS_RUN = re.compile(r"\s+")


def normalize(s: str) -> str:
    """Return a normalized copy of *s* for quote-integrity comparison.

    The transformation is symmetric -- applying it identically to both
    ``source_quote`` and ``source_text`` before ``in``-testing means
    curly-quote and whitespace differences are tolerated.

    Args:
        s: The raw string to normalize.

    Returns:
        The normalized string.
    """
    # Step 1 -- curly single quotes -> straight
    s = s.replace("‘", "'").replace("’", "'")
    # Step 2 -- curly double quotes -> straight
    s = s.replace("“", '"').replace("”", '"')
    # Step 3 -- non-breaking space -> regular space
    s = s.replace(" ", " ")
    # Step 4 -- collapse whitespace runs (includes \n, \t, \r)
    s = _WS_RUN.sub(" ", s)
    # Step 5 -- trim
    return s.strip()
