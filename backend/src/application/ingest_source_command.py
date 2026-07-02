"""IngestSourceCommand Value -- input to the IngestSource application service.

A frozen dataclass per application.md Principle 2: named after the
operation, immutable, equal by content.
"""

from dataclasses import dataclass

from src.domain.knowledge_base.jurisdiction import JurisdictionId


@dataclass(frozen=True, slots=True)
class IngestSourceCommand:
    """Command object for the IngestSource use case.

    seed_url: the authoritative URL to fetch and extract rules from.
    jurisdiction_id: the jurisdiction this run targets (UUID, for DB writes).
    jurisdiction_name: human-readable display name for prompt composition
        (INV-LLM-008). Never pass the UUID here.
    """

    seed_url: str
    jurisdiction_id: JurisdictionId
    jurisdiction_name: str
