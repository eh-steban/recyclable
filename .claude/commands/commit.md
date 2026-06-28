Commit staged and unstaged changes following project git conventions.

All commit-message and submodule rules are defined in
`.claude/docs/infra/git.md`. This command is only the procedure and does
not restate those rules, so the two cannot drift.

1. Read `.claude/docs/infra/git.md` -- ## Commit Messages and
   ## Submodules.
2. Run `git status` (never -uall) and `git diff` (staged + unstaged) to
   see what changed.
3. Run `git log --oneline -5` to match recent commit message style.
4. Draft the commit message to satisfy `git.md` ## Commit Messages.
5. Stage relevant files by name -- never `git add -A` or `git add .`,
   and never stage .env files, credentials, or large binaries.
6. If `private/` changed, follow `git.md` ## Submodules: commit inside
   the submodule first, then `git add private` so the gitlink bump lands
   in the same commit.
7. Commit via HEREDOC to preserve formatting.
8. Run `git status` to confirm success. Do not push unless asked.
