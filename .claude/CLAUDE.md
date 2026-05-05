# Recyclable

Recycling Law Assistant -- a grounded, source-cited recycling Q&A product.
Two cooperating systems share one Postgres knowledge base:

- **`frontend/`** -- Next.js App Router app. SEO-crawlable
  jurisdiction/material pages and an interactive assistant. Calls Claude
  **Sonnet** synchronously for retrieval-backed user responses.
- **`backend/`** -- Python research worker. Asynchronous source ingestion,
  extraction, conflict detection, and eval runs. Calls Claude **Opus** for
  the agentic research loop. Not on the user request path.

## Writing style

- Use `--` (double-hyphen) instead of em-dashes (`—`) in all prose, docs,
  and commit messages. Em-dash rendering depends on terminal and locale
  (`<E2><80><94>` byte sequence appears in some environments) and breaks
  across machines; the double-hyphen is portable.
- Markdown style follows `.claude/rules/markdown-style.md` (adapted from
  Google's styleguide). Soft cap of 80 columns enforced via
  `.markdownlint.json`; semantic wraps only -- no orphan lines.

## Quick reference

```bash
# Full local stack (web + worker + Postgres)
docker compose up

# Frontend only (dev mode, local Node)
cd frontend && npm run dev

# Worker only (one-off ingestion job)
cd backend && python -m app.cli ingest --source <url>

# Eval suite
cd backend && pytest tests/evals
```

## Project structure

```text
recyclable/
├── frontend/              # Next.js App Router -- SEO pages, /ask, /api/ask
├── backend/               # Python research worker -- ingestion, extraction, evals
├── docker-compose.yaml    # Local prod-shape: web + worker + Postgres
├── .devcontainer/         # Devcontainer spec (editor-agnostic; enter via ./bin/dev)
└── private/               # Strategy, experiments, specs (gitignored)
```

## Hosting target

- **Frontend:** Vercel (Next.js native; SSG + edge caching, event-driven
  revalidation on ingestion-apply).
- **Worker:** Railway (Python, Dockerfile build).
- **Database:** Neon Postgres (serverless, branching for evals).

Local Docker Compose is a dev-parity shape, not the deployment topology. The
`frontend/Dockerfile` exists for parity testing; Vercel builds Next.js itself.

## Key principles

- **Grounded answers only:** every definitive claim cites a source. The
  assistant says "I cannot verify this" rather than guess.
- **Postgres is the product asset:** structured rules drive both SEO pages
  and assistant answers. No separate hand-written content layer.
- **Sonnet on the user path, Opus on the research path:** keep the
  user-facing loop low-latency and deterministic; reserve agentic reasoning
  for offline ingestion where mistakes can be reviewed.
- **DDD inside the worker:** domain layer is pure business logic, no
  framework dependencies.
- **Fail fast:** detect errors at boundaries, refuse to answer on missing
  evidence.

## Service details

See `.claude/rules/` for detailed standards:

- `frontend/CLAUDE.md` -- Next.js App Router, route shape, SSG +
  revalidation, components
- `backend/CLAUDE.md` -- Python DDD layers, ingestion worker structure
- `llm/CLAUDE.md` -- Claude SDK usage: model selection, prompt caching,
  tool design, evals
- `data-model.md` -- Recycling knowledge base schema (jurisdictions,
  materials, rules, sources, facilities, traces)

## Coding standards

See `.claude/rules/` for detailed standards:

- `backend/` -- Python, DDD architecture, testing
- `frontend/` -- Next.js, TypeScript, testing
- `llm/` -- Claude API conventions, prompt versioning, tool schemas,
  eval harness
- `contracts.md` -- Interservice contract ownership and contract-first rule
- `doc-ownership.md` -- Which agent owns which docs/dirs (canonical)
- `refactoring.md` -- What counts as a refactor; allowed transformations
  and forbidden-by-default categories; loaded by the refactorer agent
- `validation.md` -- Evidence shape for plan validation (command, exit
  code, output excerpt, why this validates); plans link here, do not
  duplicate the discipline

Git standards live in `.claude/docs/infra/git.md`.

## Infrastructure

See `.claude/rules/infra/` for infrastructure and deployment:

- `containers.md` -- Docker images, multi-stage builds, optimization
- `docker-compose.md` -- Local development, networking, volumes
- `devcontainer.md` -- Unified development environment setup

## Error handling & observability

- `error-handling.md` -- Cross-service error philosophy, sensitive data rules
- `observability.md` -- Logging standards, log levels
- `backend/error-handling.md` -- Python exception hierarchy
- `backend/observability.md` -- Python logging setup
- `frontend/error-handling.md` -- Error types, Error Boundaries
- `llm/CLAUDE.md` -- LLM call failures, retry policy, trace logging

## Agents

Specialized subagents for autonomous work:

- `backend-python` -- Python worker: ingestion, extraction, domain services,
  eval harness, tests
- `frontend-react` -- Next.js App Router: pages, server components, route
  handlers, client components, tests
- `spec-writer` -- Specs, experiment katas, strategy docs, learnings
  consolidation
- `refactorer` -- Behavior-preserving cleanup of recently changed code
  (reads `.claude/rules/refactoring.md`)
- `code-reviewer` -- Security, convention, logic, and test coverage review
  (read-only)
- `adversarial-reviewer` -- Red-team review for invariant violations,
  auth/data boundaries, LLM grounding/injection, ingestion-time
  hostile input, and operational failure modes (read-only, opus)
- `test-auditor` -- Periodic test suite audit across all services (read-only)
- `e2e-testing` -- End-to-end tests spanning Next.js UI + worker + DB

## Workflow

Product Kata-driven development.

### Key locations

- Product strategy: `private/product/strategy/`
- Active experiments: `private/product/experiments/` (find
  `Status: active-experiment`)
- Feature specs: `private/specs/`
- Invariants: `private/invariants.md` -- non-negotiable system truths;
  cite IDs in plans, reviews, and audits when a change touches one
- Machine-switch state: `private/CONTEXT.md` (read at session start only)

### Active experiments

- `01-grounded-retrieval` -- Sonnet user path with cited answers (Denver MVP)
- `02-agentic-ingestion` -- Opus research workflow for autonomous source
  extraction

### Knowledge management

- Before starting work, check `private/learnings-index.md` for relevant
  cross-project learnings
- Full knowledge management rules: `.claude/knowledge-management.md`
- Service mental models: `.claude/rules/[service]/[service]-mental-model.md`
- If you discover a cross-project pattern, append to the `## Drafts` section
  of `private/learnings.md`
- Run `/consolidate-learnings` weekly to promote drafts (spec-writer agent)

### Shared file ownership

See `.claude/rules/doc-ownership.md` for the canonical table of which agent
owns which docs/dirs. Do not duplicate ownership rules here -- point at that
file.

### Honesty and stop conditions (all agents)

Applies to every agent in this repo. Service agents add specifics in their
own files.

- **Verify, don't invent.** If a symbol, file, API, or fact is needed and
  you cannot find it via Read/Grep or user-provided context, stop and ask --
  do not fabricate it. This is the single biggest hallucination source.
- **Stop after 3 failed attempts on the same root error.** Surface the
  failing output, your current hypothesis, and what you tried. Do not keep
  mutating code hoping it works.
- **Don't fix unrelated breakage to make CI green.** If something fails for
  reasons outside your change, pause and report.
- **Don't soften findings to be agreeable.** If a review/audit/spec turns up
  a real issue, restate the evidence when pushed back on -- don't downgrade
  severity to keep the peace. If pushback contains new evidence, update; if
  it doesn't, hold.
- **"Type-checks pass" is not "it works."** State what you actually verified
  (tests run, UI loaded in browser, query executed) versus what you only
  inferred.
- **Empty findings are valid output.** If a review/audit has nothing to flag,
  say so. Do not pad to look thorough.

### Definition of done

- Tests written and passing for new/changed code
- Observability: logging instrumented per service conventions
- Security: no sensitive data exposed, inputs validated at system boundaries
- Conventions: follows relevant `.claude/rules/[service]/CLAUDE.md` patterns
- Grounding (LLM-touching code only): every assistant answer in tests carries
  a citation; refusal path tested

**Review gates:**

1. Run `test-auditor` agent against changed services
2. Run `code-reviewer` agent against the unstaged diff
3. Fix issues before marking work complete

For quick-fixes (typos, config changes, one-line edits): self-review is
sufficient.

**Plan review gate:** after writing/revising a spec or kata, run `spec-writer`
agent to review.

### Development principles

- NEVER build without a linked experiment defining the outcome we're targeting
- Specs require task shards -- atomic units a subagent can execute
  independently
- Each experiment step must be ≤ 1 week
- Use `/kata-check` weekly to review experiment progress
- Use `/quick-fix` for bugs and small changes (skip experiment/spec ceremony)

### Before starting any feature work

1. Check `private/product/experiments/` for the active experiment
2. Read the current experiment's `kata.md` -- what step are we on?
3. If building: find the spec in `private/specs/` with task shards
4. Work from a single task shard -- don't load the full spec into context
5. After completing a shard: run the "Verify before proceeding" check

### Context budgets

Full budget reference:
`.claude/skills/context-audit/references/context-budgets.md`

- Clear at 30%: Quality degrades noticeably past 30% context utilization
- MCP servers: maximum 3 active simultaneously
