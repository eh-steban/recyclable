---
paths:
  - "frontend/lib/llm/**/*.ts"
  - "backend/src/llm/**/*.py"
  - "backend/src/application/use_cases/**/*.py"
---

# LLM Conventions (Claude SDK)

Standards for every Claude API call in this project, on either side.
The user-facing path uses **Sonnet**; the offline research path uses
**Opus**. Direct Anthropic SDK calls only -- no LangChain, no agent
frameworks.

## Model selection

| Path | Model | Rationale |
| --- | --- | --- |
| `/api/ask` user retrieval (frontend) | `claude-sonnet-4-6` | Low-latency, deterministic synthesis bounded by retrieved context |
| Material normalizer fallback (frontend) | `claude-haiku-4-5-20251001` | Cheap classification only when alias matching fails |
| Source extraction / ingestion (backend) | `claude-opus-4-7` | Higher reasoning for messy real-world pages; offline so latency does not matter |
| Regression-suite grader (backend) | `claude-sonnet-4-6` | Consistent rubric scoring |

Pin model IDs at the call site -- never read them from user input. Model
upgrades are deliberate, reviewed changes.

## Prompt versioning

Every prompt template has:

- A stable name (`ask_compose_v1`, `extract_rules_v1`,
  `material_normalize_v1`).
- A version integer that increments on any wording, schema, or example
  change.
- A pure builder function that returns the full message array given inputs.
- The version logged on every call so traces map back to the exact prompt.

```ts
// frontend/lib/llm/prompts/ask-compose.ts
export const ASK_COMPOSE_VERSION = 1;
export function buildAskComposeMessages(input: AskComposeInput): Message[] {
  // ...
}
```

```python
# backend/src/llm/prompts/extract_rules.py
EXTRACT_RULES_VERSION = 1
def build_extract_rules_messages(input: ExtractRulesInput) -> list[Message]:
    ...
```

When you change a prompt: bump the version, update the regression suite
(or note why it does not need an update), and ensure the validator still
applies.

## Prompt caching

Use Anthropic's prompt caching for all calls with stable prefixes. The
system prompt, tool definitions, and any large reference context (taxonomy,
source authority order) belong in cached blocks. The variable user query
goes after.

- Frontend `/api/ask`: cache the system prompt + answer schema. Per-call
  cost is the user query + retrieved context.
- Backend extraction: cache the system prompt + extraction schema +
  jurisdiction context. Per-call cost is the source document text.
- Set `cache_control: { type: 'ephemeral' }` on the appropriate content
  blocks. Verify cache hit rate in traces.

If a prompt is called fewer than 2-3 times within the 5-minute TTL window,
caching is wasted overhead -- skip it.

## Tool design

Tools must be:

- **Narrow**: one verb, one return type. `search_rules(jurisdiction_id,
  material_id)` not `search_anything(query)`.
- **Typed**: zod (TS) or Pydantic (Python) on LLM structured inputs and
  outputs. Validate the model's response before trusting it for citations
  or downstream use -- a malformed tool-call response should fail fast, not
  silently corrupt downstream logic.
- **Idempotent where possible**: `fetch_source(url)` returns the same
  payload for the same URL given an unchanged page.
- **Side-effect-free during user Q&A**: the user-path tools only read.
  Writes happen in operator-approved ingestion flows.

User-facing tool surface (frontend):

```text
resolve_location(city_or_zip) -> jurisdiction
normalize_material(query) -> { candidates, ambiguous }
search_rules(jurisdiction_id, material_id) -> rules[]
search_sources(jurisdiction_id, query) -> source_chunks[]
find_facilities(jurisdiction_id, material_id) -> facilities[]
compose_answer(query, retrieved_context) -> AnswerDraft
validate_answer(answer, retrieved_context) -> { ok, issues }
```

Operator/research tool surface (backend):

```text
fetch_source(url) -> SourceDocument
extract_rules(source_document) -> CandidateRule[]
diff_source(previous, current) -> SourceDiff
run_regression_suite(suite_id) -> { scores, failures }
```

The agent must not browse freely during user Q&A. Browsing belongs in
operator-triggered ingestion or a clearly-marked deep-research fallback.

## Answer schema (user path)

Every `/api/ask` response conforms to:

```ts
type Answer = {
  short_answer: 'yes' | 'no' | 'conditional' | 'unknown';
  recommended_action: string;
  preparation_steps: string[];
  do_not_do: string[];
  dropoff_options: Facility[];
  confidence: 'high' | 'medium' | 'low';
  citations: { title: string; url: string; quote?: string }[];
  clarifying_question: string | null;
  jurisdiction: { id: string; name: string };
  trace_id: string;
};
```

The model returns this shape directly. The validator runs after and may
downgrade `confidence` or convert the answer to `unknown` if grounding
fails.

## Validator (mandatory after every user-path call)

Block or downgrade the answer if any of:

- No citation attached and `short_answer` is definitive.
- Retrieved source's jurisdiction does not match the requested one.
- Answer says "accepted" while the retrieved rule says "rejected".
- Material normalization is ambiguous and the answer does not include
  `clarifying_question`.
- Source `authority_level` is below threshold for a definitive claim.
- Source `last_reviewed_at` is older than 12 months -- downgrade to
  `medium` and surface a freshness note.

Validator failures are logged, the answer is rewritten or downgraded,
and the trace records the original + final state.

## Prompt-injection and tool access

Three durable principles for every LLM boundary in this project.
Step 2 specifics are in `private/specs/01-sonnet-user-path.md`
§ Prompt-injection defense (Step 2 baseline).

- **Destructive capability is gated by the tool surface, not by prompt
  instruction.** If a capability should not be reachable from the LLM,
  it must not appear in the tool registry. Prompt instructions saying
  "do not use this" are not a security boundary. On the user path,
  Sonnet's registered tools are read-only; no write path is
  registered.
- **Untrusted text is always delimited as data.** User-supplied input
  is wrapped in explicit delimiters (e.g. XML tags) and placed in the
  user turn, never concatenated into the system prompt or into
  instruction blocks. This operationalises INV-LLM-004.
- **Length caps on user input are required at every LLM boundary.**
  Long payloads are the primary prompt-bombing vector. Each endpoint
  that feeds user text to a model must enforce a character limit at
  the HTTP layer, before the text reaches the prompt builder. The
  limit for `POST /ask` is 500 characters.

## Error handling and retries

- Timeout: 20s per Anthropic call (user path). 120s per call (research
  path).
- Retry: at most 1 retry on 429 / 5xx, exponential backoff with jitter.
  Never retry on 4xx other than 429.
- On final failure: return a structured "unable to verify right now, try
  again" answer with a captured trace, not a stack trace.
- Never expose raw model output that failed schema validation to the user.
  Refuse instead.

## Trace persistence

Every model call writes an `AnswerAuditRecord` (user path) or `IngestionReport`
(research path) row, with at minimum:

- `prompt_name`, `prompt_version`, `model_id`.
- Input summary (query, jurisdiction, normalized material).
- Tool calls in order with inputs/outputs.
- Final raw model output and validator result.
- Latency, token counts, cache hit/miss.

Traces are the debugging surface. "Read the logs" without a trace is not
enough.

## Secrets

`ANTHROPIC_API_KEY` only via env. Never log it, never bundle it
client-side. Keys differ per environment (dev / preview / prod) -- preview
Vercel deploys should use a budget-capped key.

## Regression suite

See `regression-suite.md` in this directory.
