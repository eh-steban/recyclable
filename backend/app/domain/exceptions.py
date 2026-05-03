"""Domain-layer exceptions. All are pure Python -- no framework imports."""

import textwrap


class DomainError(Exception):
    """Base class for all domain errors."""


class EntityNotFoundError(DomainError):
    """A required entity does not exist."""

    entity_type: str
    identifier: str

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")


class SeedIntegrityError(DomainError):
    """source_quote is not a substring of the source document's source_text."""

    rule_slug: str
    quote_excerpt: str

    def __init__(self, rule_slug: str, quote_excerpt: str) -> None:
        self.rule_slug = rule_slug
        self.quote_excerpt = quote_excerpt
        wrapped = textwrap.fill(
            quote_excerpt,
            width=80,
            initial_indent="  ",
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        )
        msg = (
            f"Quote integrity violation for rule '{rule_slug}': "
            f"normalized quote not found in normalized source_text:\n{wrapped}"
        )
        super().__init__(msg)


class SeedSchemaError(DomainError):
    """Fixture content does not match the domain model schema."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Seed schema error: {message}")
