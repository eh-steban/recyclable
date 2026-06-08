Audit comments and docstrings for misplaced knowledge using the
comment-reviewer subagent.

Find comments and docstrings that carry knowledge belonging in a higher
tier -- architecture/pattern decisions, cross-service patterns, feature
assumptions, experiment outcomes -- instead of staying a 1-3 line
Tier 5 pointer. Report a redistribution plan: where each chunk should
move, the trimmed inline replacement, and which owner applies it.

Use the comment-reviewer agent for this work. It is read-only -- it
drafts relocations; spec-writer and the service agents apply them under
`.claude/rules/doc-ownership.md`.

Scope:

- Default (no argument): diff mode -- review only comments/docstrings
  in the current unstaged + staged diff. Use this as a PR review step
  alongside `/code-review`.
- `--sweep [path]`: sweep mode -- audit existing comments across the
  given path (default: whole repo). Use this to work down the backlog
  of over-stuffed docstrings.

Recommended cadence: diff mode per PR touching commented code; sweep
mode monthly, or before a release, like `/test-audit`.
