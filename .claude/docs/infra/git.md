# Git Standards

Commit messages follow [Conventional Commits][cc-spec]; branch names
follow [Conventional Branch][cb-spec]. The format rules in those specs
are the canonical source -- this file lists only the **project deltas**:
the type sets we use, project-specific rules the specs do not cover,
and links to where each rule is enforced.

[cc-spec]: https://www.conventionalcommits.org/
[cb-spec]: https://conventional-branch.github.io/

## Enforcement

- **Local `git commit`** -- `conventional-pre-commit` (type / format) +
  `bin/check-commit-msg` (project rules), wired in
  `.pre-commit-config.yaml` at the `commit-msg` stage.
- **Local `git push`** -- `bin/check-branch-name`, wired at the
  `pre-push` stage.
- **CI on every PR** -- `.github/workflows/commit-msg.yml` re-runs the
  same `commit-msg` hooks against every commit on the PR branch, so
  locally-bypassed commits are caught at PR time.

Run `pre-commit install --hook-type pre-commit --hook-type commit-msg
--hook-type pre-push` once per clone, or use `bin/dev` (auto-installs).

---

## Commit Messages

### Allowed types

| Type | When to Use |
| :------ | :------------- |
| `feat` | New user-facing feature (SemVer MINOR) |
| `fix` | Bug fix (SemVer PATCH) |
| `refactor` | Code restructuring without behavior change |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Tooling, dependencies, build process |
| `ci` | CI/CD pipeline changes |

The list above is mirrored verbatim in `.pre-commit-config.yaml` under
`conventional-pre-commit`'s `args:`. If you add a type here, add it
there too.

### Project rules (in addition to the spec)

These are not enforced by `conventional-pre-commit`. The first three
are checked by `bin/check-commit-msg`; the rest are guidance for
humans and agents.

- Subject line MUST NOT exceed **72 characters** total.
- MUST NOT append `Co-Authored-By`, `Signed-off-by`, `Reviewed-by`,
  `Acked-by`, or any attribution footer.
- MUST NOT contain em-dashes (`—`); use `--` (double-hyphen). See
  `.claude/CLAUDE.md` ## Writing style for the rationale.
- Scope (when present) MUST be lowercase and describe a service or
  area: `feat(parser): ...`, `fix(frontend): ...`, `chore(backend): ...`.
- Description MUST be in imperative mood: "add", "fix", "remove" --
  not "added", "fixes", "removing".
- Body is OPTIONAL. Omit it for changes whose subject line is
  self-explanatory (one-file edits, obvious renames). When included:
  precede with a blank line; bullets convey impact, not mechanics;
  three to four bullets is enough.
- Describe **what** changed and **why**, not **how**. Implementation
  details belong in code comments or PR descriptions, not commit
  subjects.

### What to write

Each block contrasts a good subject with a bad one for the same change.

- **Good:** `feat: add lane pressure visualization`
  **Bad:** `feat: add LanePressureChart component that uses useMemo to
  memoize filtered array`
  -- the bad form names internal symbols and APIs.
- **Good:** `fix: correct creep wave count off-by-one`
  **Bad:** `fix: change <= 4 to < 4 in creep entity loop condition`
  -- the bad form describes the diff, not the user-visible behavior.
- **Good:** `feat(parser): expose boss state in output`
  **Bad:** `feat(parser): add boss_snapshots: Vec<BossSnapshot> field
  and serialize with serde`
  -- the bad form leaks types and library names.
- **Good:** `chore: upgrade parser dependencies`
  **Bad:** `chore: run cargo update and bump serde from 1.0.195 to
  1.0.197`
  -- the bad form rots the moment the version moves.

---

## Branch Names

Format: `<type>/<description>` per [Conventional Branch][cb-spec].

### Allowed types

| Type | When to Use |
| :------ | :------------- |
| `feature/` | New feature work |
| `fix/` | Bug fix |
| `hotfix/` | Urgent production fix |
| `release/` | Release preparation |
| `chore/` | Tooling, deps, maintenance |

The list above is mirrored in `bin/check-branch-name`'s regex. If you
add a type here, update the regex too.

### Project rules (in addition to the spec)

Enforced by `bin/check-branch-name`:

- Description MUST be lowercase, using only `a-z`, `0-9`, and hyphens.
- No consecutive hyphens, no leading or trailing hyphens.
- Dots are permitted **only** in `release/` branches, for version
  numbers: `release/v1.2.0`.

Project conventions (not enforced):

- Include a ticket number when applicable:
  `feature/issue-123-login-flow`.

### Examples

```text
feature/player-lane-pressure
fix/parse-timing
hotfix/security-patch
release/v1.2.0
chore/upgrade-parser-deps
feature/issue-42-souls-tracking
```

### `scripts/wt` integration

`wt create <name>` defaults the branch to `feature/<name>`. Pass an
explicit second arg for other types:

```bash
scripts/wt create fix-parse-timing fix/parse-timing        # fix/ branch
scripts/wt create souls feature/souls-tracking             # explicit feature/
scripts/wt create release-v2 release/v2.0.0               # release/ with version
```
