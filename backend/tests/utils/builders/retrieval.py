"""Builders for retrieval Values (Citation, EvaluatedAnswer)."""

from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import EvaluatedAnswer
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    ItemVerdict,
    Refused,
)


def make_citation(
    *,
    url: str = "https://denvergov.org/recycling",
    title: str = "Denver Recycling Guide",
    quote: str | None = None,
) -> Citation:
    return Citation(title=title, url=url, quote=quote)


def make_evaluated_answer(
    *,
    verdict: ItemVerdict | None = None,
    citations: tuple[Citation, ...] | None = None,
    recommended_action: str = "Place in the blue bin.",
    confidence: str = "high",
    retrieved_source_urls: frozenset[str] | None = None,
    preparation_steps: tuple[str, ...] = (),
    do_not_do: tuple[str, ...] = (),
    clarifying_question: str | None = None,
) -> EvaluatedAnswer:
    if citations is None:
        citations = (make_citation(),)
    # Thread citations into the verdict (citations live on the verdict per
    # architecture.md § ItemVerdict). NotCovered carries no citations.
    _verdict = verdict if verdict is not None else Accepted()
    if isinstance(_verdict, Accepted):
        _verdict = Accepted(conditions=_verdict.conditions, citations=citations)
    elif isinstance(_verdict, Refused):
        _verdict = Refused(citations=citations)
    elif isinstance(_verdict, Conflicted):
        _verdict = Conflicted(citations=citations)
    if retrieved_source_urls is None:
        retrieved_source_urls = frozenset(c.url for c in citations)
    return EvaluatedAnswer(
        verdict=_verdict,
        recommended_action=recommended_action,
        confidence=confidence,
        retrieved_source_urls=retrieved_source_urls,
        preparation_steps=preparation_steps,
        do_not_do=do_not_do,
        clarifying_question=clarifying_question,
    )
