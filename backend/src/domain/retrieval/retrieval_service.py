"""RetrievalService Domain Service: Sonnet user-path choreography."""

import logging
from dataclasses import replace
from typing import final

from src.domain.knowledge_base.jurisdiction import Jurisdiction
from src.domain.knowledge_base.material_normalizer import MaterialNormalizer
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    Uncertain,
)
from src.domain.knowledge_base.rule import AcceptedStatus
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.domain.knowledge_base.source_repo import SourceRepo
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.grounding_validator import GroundingValidator
from src.domain.retrieval.prompt_composer import (
    ask_compose_v1,
    format_rule_context,
)
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import RetrievalLLM

logger = logging.getLogger(__name__)

#: User-facing message for all VALIDATOR_REJECTED outcomes.
_VALIDATOR_REJECTED_MSG = (
    "The answer could not be grounded in the retrieved sources."
)


@final
class RetrievalService:
    """Domain Service: composes the Sonnet user-path choreography.

    Takes ports as constructor parameters (MaterialNormalizer, RuleRepo,
    SourceRepo, RetrievalLLM) so that the Application Service can inject
    concrete implementations via FastAPI Depends without the domain
    importing infrastructure.

    Location resolution is the caller's responsibility: ``answer`` receives
    the already-resolved Jurisdiction (or None for out-of-jurisdiction), so
    the user path resolves the location exactly once per request.
    """

    def __init__(
        self,
        material_normalizer: MaterialNormalizer,
        rule_repo: RuleRepo,
        source_repo: SourceRepo,
        retrieval_llm: RetrievalLLM,
    ) -> None:
        self._material_normalizer = material_normalizer
        self._rule_repo = rule_repo
        self._source_repo = source_repo
        self._retrieval_llm = retrieval_llm
        self._grounding_validator = GroundingValidator()

    def answer(
        self, query: Query, jurisdiction: Jurisdiction | None
    ) -> EvaluatedAnswer | NoEvaluation:
        if jurisdiction is None:
            logger.info(
                "out of jurisdiction: location=%r", query.location_input
            )
            return NoEvaluation(
                reason=NoEvaluationReason.OUT_OF_JURISDICTION,
                recommended_action=(
                    f"{query.location_input!r} is not yet supported. "
                    "Recyclable currently covers Denver only."
                ),
            )

        normalization = self._material_normalizer.normalize(query.text)

        if isinstance(normalization, Uncertain):
            logger.info(
                "material normalization uncertain: query=%r", query.text
            )
            return NoEvaluation(
                reason=NoEvaluationReason.UNCERTAIN_MATERIAL,
                recommended_action=(
                    "We couldn't identify a material in your query. "
                    "Try rephrasing with the item's name."
                ),
                clarifying_question=(
                    "Which material are you asking about? "
                    "Please be more specific."
                ),
            )

        if isinstance(normalization, Ambiguous):
            logger.info(
                "material normalization ambiguous: query=%r, candidates=%d",
                query.text,
                len(normalization.candidates),
            )
            candidate_names = ", ".join(
                c.canonical_name for c in normalization.candidates
            )
            return NoEvaluation(
                reason=NoEvaluationReason.AMBIGUOUS_MATERIAL,
                recommended_action=(
                    f"Several materials match your query: {candidate_names}."
                ),
                clarifying_question=f"Did you mean one of: {candidate_names}?",
            )

        material_id = normalization.material.id

        rules = self._rule_repo.find_for(jurisdiction.id, material_id)
        if not rules:
            logger.info(
                "no rules for jurisdiction=%s material=%s",
                jurisdiction.id,
                material_id,
            )
            return NoEvaluation(
                reason=NoEvaluationReason.NO_EVIDENCE,
                recommended_action=(
                    "No recycling rule found for this material in "
                    "the queried jurisdiction."
                ),
            )

        # UNKNOWN status states no disposition: the model could still cite
        # the rule, yielding a groundless but citable verdict. Refuse as
        # missing evidence (INV-PROD-001). find_for returns one rule (LIMIT 1).
        if rules[0].accepted_status == AcceptedStatus.UNKNOWN:
            logger.info(
                "UNKNOWN-status rule: jurisdiction=%s material=%s",
                jurisdiction.id,
                material_id,
            )
            return NoEvaluation(
                reason=NoEvaluationReason.NO_EVIDENCE,
                recommended_action=(
                    "No conclusive recycling rule is available for this "
                    "material in the queried jurisdiction."
                ),
            )

        # INV-LLM-002: the retrieved source set is the only set of URLs the
        # model may cite; it is built here once and reused for the rule
        # context block and the grounding check (no extra DB call).
        sources_by_id: dict[SourceId, SourceDocument] = {}
        for source_id in {rule.source_document_id for rule in rules}:
            doc = self._source_repo.find_by_id(source_id)
            if doc is not None:
                sources_by_id[doc.id] = doc
        retrieved_source_urls: frozenset[str] = frozenset(
            doc.url for doc in sources_by_id.values()
        )

        rule_context = format_rule_context(rules, sources_by_id)
        prompt = ask_compose_v1(query, rule_context)
        llm_result = self._retrieval_llm.ask(
            list(prompt.messages), prompt.system_prompt
        )

        if isinstance(llm_result, NoEvaluation):
            logger.warning(
                "LLM returned NoEvaluation: reason=%s", llm_result.reason
            )
            return llm_result

        violations = self._grounding_validator.validate(
            llm_result.verdict,
            retrieved_source_urls,
        )
        if violations:
            logger.warning(
                "grounding violations: %s",
                [v.code for v in violations],
            )
            return NoEvaluation(
                reason=NoEvaluationReason.VALIDATOR_REJECTED,
                recommended_action=_VALIDATOR_REJECTED_MSG,
            )

        return replace(llm_result, retrieved_source_urls=retrieved_source_urls)

    def fallback_for_validator_rejection(self, query: Query) -> NoEvaluation:
        """Return a NoEvaluation(VALIDATOR_REJECTED) for construction-time
        grounding failures.

        """
        logger.info("fallback_for_validator_rejection: query=%r", query.text)
        return NoEvaluation(
            reason=NoEvaluationReason.VALIDATOR_REJECTED,
            recommended_action=_VALIDATOR_REJECTED_MSG,
        )
