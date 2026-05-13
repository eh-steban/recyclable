"""Citation Value -- a source reference attached to an answer."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Citation:
    """A source citation in a retrieval answer.

    url must be a member of the retrieved-source-URL set (INV-LLM-002).
    The domain never authors URLs; citations are joined from the source
    documents that backed rule extraction.
    """

    title: str
    url: str
    quote: str | None = None

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("citation url must be non-empty")
        if not self.title:
            raise ValueError("citation title must be non-empty")
