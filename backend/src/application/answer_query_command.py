"""AnswerQueryCommand Value -- input to the AnswerQuery application service.

A frozen dataclass per application.md Principle 2: named after the
operation, immutable, equal by content, fields are plain strings.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnswerQueryCommand:
    """Command object for the AnswerQuery use case.

    query_text: the raw user question (max 500 chars, enforced by
    the HTTP layer before the command is constructed).
    location_input: the raw user location string.
    """

    query_text: str
    location_input: str
