# Recyclable

Recycling Law Assistant -- grounded, source-cited recycling Q&A. Two
cooperating systems share one Postgres knowledge base:

- **`frontend/`** -- Next.js App Router app. SEO-crawlable
  jurisdiction/material pages and an interactive assistant. Claude
  **Sonnet** on the user path.
- **`backend/`** -- Python research worker. Asynchronous source ingestion,
  extraction, regression-suite runs. Claude **Opus** for the agentic
  research loop.

See `recycling-agent-experiment-spec.md` for the full strategy doc, and
`private/product/strategy/vision.md` for the working vision.

## Quick Start

```bash
cp .env.example .env
# edit .env -- ANTHROPIC_API_KEY is required
docker compose up
```

- Frontend: <http://localhost:3000>
- Worker admin: <http://localhost:8000>
- Postgres: `localhost:5432` (user `recyclable`, db `recyclable`)

## Pre-commit hooks

This repo uses [pre-commit][pre-commit] to run [gitleaks][gitleaks]
(secret scanner), `ruff` / `prettier` formatters, and commit-message
validation against `.claude/docs/infra/git.md`. One-time setup per
machine:

[pre-commit]: https://pre-commit.com
[gitleaks]: https://github.com/gitleaks/gitleaks

```bash
pip install pre-commit       # or: pipx install pre-commit
pre-commit install --hook-type pre-commit \
                   --hook-type commit-msg \
                   --hook-type pre-push
```

`bin/dev` runs the same install on entry, so contributors who use the
dev-container script get hooks installed automatically.

After that, `git commit` will scan the staged diff for accidentally-committed
API keys / tokens, reject commit messages that violate the project git
rules (wrong type, subject too long, attribution footers, em-dashes), and
`git push` will reject branch names that don't match conventional-branch
format. The same commit-msg checks also run in CI as a merge gate, so
locally-bypassed commits are caught at PR time.

To run against the full repo on demand:

```bash
pre-commit run --all-files
```

If gitleaks flags a false positive (e.g. a fake key in a test fixture), add
an allowlist entry to `.gitleaks.toml` rather than disabling the hook.
