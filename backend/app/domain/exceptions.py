"""Domain-layer exceptions. All are pure Python -- no framework imports."""


class DomainError(Exception):
    """Base class for all domain errors."""


class EntityNotFoundError(DomainError):
    """A required entity does not exist."""

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")


class SeedIntegrityError(DomainError):
    """A rule's source_quote is not a substring of its source document's source_text."""

    def __init__(self, rule_slug: str, quote_excerpt: str) -> None:
        self.rule_slug = rule_slug
        self.quote_excerpt = quote_excerpt
        super().__init__(
            f"Quote integrity violation for rule '{rule_slug}': "
            f"normalized quote '{quote_excerpt[:80]}...' "
            "not found in normalized source_text"
        )


class SeedSchemaError(DomainError):
    """Fixture content does not match the domain model schema."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Seed schema error: {message}")
