"""Query Value -- the user's recycling question."""

from dataclasses import dataclass

#: Maximum query length enforced at the HTTP boundary (INV-LLM-004).
#: 150 sits well above any genuine recycling question while keeping
#: the worst-case prompt-injection payload small.
QUERY_MAX_LENGTH = 150


@dataclass(frozen=True, slots=True)
class Query:
    """The user's recycling question and location input.

    Attribute-level guards enforce the length cap here so that the domain
    can never process an over-long query regardless of which adapter
    constructed it.
    """

    text: str
    location_input: str

    def __post_init__(self) -> None:
        if len(self.text) > QUERY_MAX_LENGTH:
            raise ValueError(
                f"query text exceeds max length of {QUERY_MAX_LENGTH} "
                + f"characters (INV-LLM-004); got {len(self.text)}"
            )
        if not self.text.strip():
            raise ValueError("query text must not be blank")
