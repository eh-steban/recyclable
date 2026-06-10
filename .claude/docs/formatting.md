# Code Formatting

Single line-length budget across both services: **80 columns**.

Source of truth for each toolchain:

- Python: `backend/pyproject.toml` `[tool.ruff] line-length = 80`
- TypeScript / JavaScript / JSON / CSS: `frontend/.prettierrc.json`
  `"printWidth": 80`

A pre-commit hook (`.pre-commit-config.yaml`) runs `ruff format` and
`prettier --write` against staged files. Unformatted code cannot land.

## Agent responsibilities

Before reporting a coding task as done, run the formatter for the files
you changed:

```bash
# Backend (from backend/)
ruff format <changed paths>
ruff check --fix <changed paths>

# Frontend (from frontend/)
npx prettier --write <changed paths>
```

If the formatter rewrites a line you wrote, accept the rewrite -- do not
hand-restructure to fight the tool. If a single statement genuinely
cannot be made readable at 80 columns (long URL string, generated SQL,
import path), wrap at a semantic boundary or, as a last resort, suppress
on that line with a narrow `# noqa: E501` / `// prettier-ignore` and
note why.

Do not change `line-length` / `printWidth` per-file. If the cap is wrong
for the whole project, raise it as a separate change with rationale --
not as a side effect of another task.

## Markdown

Markdown follows `.claude/rules/markdown-style.md` (semantic wrap at
~80, not formatter-enforced). Prettier is wired to format markdown in
`frontend/` only; outside that tree, wrap by hand per the style guide.
