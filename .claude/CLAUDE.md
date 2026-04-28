# [Project Name]

[Brief description of your project]

## Writing Style

- Use `--` (double-hyphen) instead of em-dashes (`—`) in all prose, docs, and commit messages. Em-dashes render as `<E2><80><94>` in git diffs and some terminals.
- Never hard-wrap prose lines in markdown files. Do not insert manual line breaks mid-sentence. Let lines be as long as needed -- editors and renderers handle wrapping. Hard-wrapped lines with continuation indents double-wrap in terminals and look broken.

## Quick Reference

```bash
# Full stack (all services + database)
docker-compose up
```

## Project Structure

```
project-root/
├── backend/          # Python/FastAPI - API, business logic, storage
├── frontend/         # React/TypeScript - Web app
├── docker-compose.yaml
```

## Key Principles

- **DDD Architecture:** Domain layer is pure business logic, no framework dependencies
- **API Advisement:** Avoid translation layers between internal/external schemas where possible
- **Fail Fast:** Detect errors early, handle them gracefully
- **SOLID Principles:** Apply across all services -- each service CLAUDE.md has service-specific thresholds and DIP guidance

## Service Details

See `.claude/rules/` for detailed standards:
- `backend/CLAUDE.md` -- Structure, commands, DDD layers
- `frontend/CLAUDE.md` -- Structure, commands, components

## Coding Standards

See `.claude/rules/` for detailed standards:
- `backend/` -- Python, DDD architecture, testing
- `frontend/` -- React, TypeScript, testing
- `contracts.md` -- Interservice contract ownership and contract-first rule

Git standards live in `.claude/docs/infra/git.md`.

## Infrastructure

See `.claude/rules/infra/` for infrastructure and deployment:
- `containers.md` -- Docker images, multi-stage builds, optimization
- `docker-compose.md` -- Local development, networking, volumes
- `devcontainer.md` -- Unified development environment setup

## Error Handling & Observability

See `.claude/rules/` for error handling and observability standards:
- `error-handling.md` -- Cross-service error philosophy, categories, sensitive data rules
- `observability.md` -- Logging standards, log levels
- `backend/error-handling.md` -- Python exception hierarchy, HTTP status mapping
- `backend/observability.md` -- Python logging setup, required log points
- `frontend/error-handling.md` -- Error types, Error Boundaries, graceful degradation

## Agents

Specialized subagents for autonomous work:
- `backend-python` -- Python/FastAPI: endpoints, use cases, domain services, backend tests
- `frontend-react` -- React/TypeScript: components, hooks, state, frontend tests
- `spec-writer` -- Specs, experiment katas, strategy docs, learnings consolidation
- `code-reviewer` -- Security, convention, logic, and test coverage review (read-only)
- `test-auditor` -- Periodic test suite audit across all services (read-only)
- `e2e-playwright` -- Cross-service end-to-end tests spanning full user flows

## Workflow

This project uses a Product Kata-driven development workflow.

### Key Locations
- Product strategy: `private/product/strategy/`
- Active experiments: `private/product/experiments/` (find `Status: active-experiment`)
- Feature specs: `private/specs/`
- Machine-switch state: `private/CONTEXT.md` (read at session start only)

### Knowledge Management
- Before starting work, check `private/learnings-index.md` for relevant cross-project learnings
- Full knowledge management rules: `.claude/knowledge-management.md`
- Service mental models: `.claude/rules/[service]/[service]-mental-model.md`
- If you discover a cross-project pattern, append to `private/learnings.md` ## Drafts section
- Run `/consolidate-learnings` weekly to promote drafts (spec-writer agent)

### Shared File Ownership
- Strategy files (`vision.md`, `current-options.md`): spec-writer agent only
- `private/learnings-index.md`: spec-writer only (updated during `/consolidate-learnings`)
- `private/learnings.md` (promoted entries): spec-writer only
- `private/learnings.md` ## Drafts: any service agent may append

### Definition of Done (applies to ALL work)
Every completed unit of work must meet these standards:
- Tests written and passing for new/changed code
- Observability: logging instrumented per service conventions
- Security: no sensitive data exposed, inputs validated at system boundaries
- Conventions: follows relevant `.claude/rules/[service]/CLAUDE.md` patterns

**Review gates (run automatically after each logical unit of work):**

After completing an implementation phase, feature shard, or significant refactor:
1. Run `test-auditor` agent against changed services -- catch coverage gaps, missing error path tests, stale tests
2. Run `code-reviewer` agent against the unstaged diff -- catch convention violations, security issues, logic bugs
3. Fix any issues from steps 1-2 before marking work complete

For quick-fixes (typos, config changes, one-line edits): self-review is sufficient, skip auditor/reviewer.

**Plan review gate (run after writing or substantially revising a plan):**

After writing a spec, experiment kata, or implementation plan:
1. Run `spec-writer` agent to review the plan for template alignment, completeness, measurable acceptance criteria, learnings citations, and contract field coverage
2. Fix any structural issues before proceeding to implementation

### Development Principles
- NEVER build without a linked experiment defining the outcome we're targeting
- Specs require task shards -- atomic units a subagent can execute independently
- Each experiment step must be ≤ 1 week
- Use `/kata-check` weekly to review experiment progress
- Use `/quick-fix` for bugs and small changes (skip experiment/spec ceremony)

### Before Starting Any Feature Work
1. Check `private/product/experiments/` for the active experiment
2. Read the current experiment's `kata.md` -- what step are we on?
3. If building: find the spec in `private/specs/` with task shards
4. Work from a single task shard -- don't load the full spec into context
5. After completing a shard: run the "Verify before proceeding" check

### Context Budgets
Full budget reference: `.claude/skills/context-audit/references/context-budgets.md`
- Clear at 30%: Quality degrades noticeably past 30% context utilization
- MCP servers: maximum 3 active simultaneously
