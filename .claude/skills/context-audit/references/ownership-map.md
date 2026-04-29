# Ownership Map

> **This file is now a pointer.** The canonical ownership table lives at `.claude/rules/doc-ownership.md`. Read that file.

The `context-audit` skill categorizes findings using the four ownership classes defined in `doc-ownership.md`:

- **Spec-writer owned** -- skill may auto-apply after approval.
- **Service agent owned** / **Append-only** -- skill flags for the relevant service agent.
- **Owner-only** -- skill outputs diffs but does NOT auto-apply (architectural/workflow decisions).
- **Shared / no single owner** -- normal review gates.

When the skill walks the file tree, match each path against the tables in `doc-ownership.md` to decide which class it falls into.

If you find yourself wanting to edit the ownership rules, edit `doc-ownership.md`, not this file. This file should stay a thin pointer to prevent the drift problem that motivated the consolidation in the first place.
