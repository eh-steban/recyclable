# Worktree awareness

Read this before reading any file. This repo uses git worktrees and
branches the `private/` submodule per worktree, so an agent that reads the
wrong checkout sees stale content and draws false conclusions.

## Why this matters

Your session's default working directory may be a *different* checkout
than the plan you are working under. That checkout's `private/`
(invariants, specs, plans) and source can be stale -- missing branch-only
content -- because `main` lags the feature branch. A relative-path read
from the wrong checkout yields false "does not exist" findings (a reviewer
once reported a real invariant as "fabricated" because it read `main`'s
copy).

## What to do

1. **Resolve your worktree first.** If your task gives an absolute
   worktree path, use it. Otherwise grep only the plan's frontmatter for
   its branch -- `grep -m1 '^\*\*Branch:\*\*' <plan>` -- then
   `git worktree list` and match that branch to its path. Do not read the
   whole plan to find this.
2. **Read every file from that worktree by absolute path** -- `private/`
   (invariants, specs, plans) and source alike. Never trust a relative
   path resolved from the session cwd.
3. **When you read part of a plan, read your full section by its real
   bounds -- not a guessed length.** Map the plan cheaply with
   `grep -n '^## ' <plan>` (every section heading and its line number, no
   body). A worker that owns one or more user stories reads from its
   `## Story N -- ...` heading to the line before the next `## ` heading
   (its full range, however long). A fixed N-line window is a guess that
   truncates the section.
4. **On an empty grep for a cited invariant, spec, or rule ID, report
   "not found at `<path>` -- verify the worktree/branch", never
   "fabricated".**
