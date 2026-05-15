"""Wire -> domain mapper for the user path.

Translates AskRequest to AnswerQueryCommand. Pure translation;
no validation (the route layer enforces caps and INV-LLM-004).
"""

from src.api.schemas.answer import AskRequest
from src.application.answer_query_command import AnswerQueryCommand


def ask_request_to_command(request: AskRequest) -> AnswerQueryCommand:
    """Translate an AskRequest wire schema to an AnswerQueryCommand."""
    return AnswerQueryCommand(
        query_text=request.query,
        location_input=request.location,
    )
