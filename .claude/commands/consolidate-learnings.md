Consolidate draft learnings and revise project documentation files. Use the
spec-writer agent. This command combines draft promotion with session-end file
revision.

## Part 1: Promote drafts

1. Read private/learnings.md -- check the ## Drafts section for pending
   entries
2. For each draft:
   - Is this a genuine cross-project pattern (2+ occurrences)?
   - Does it duplicate an existing promoted learning?
   - Is the finding accurate and well-described?
3. Promote valid drafts: move from ## Drafts to the appropriate section above,
   following the standard learning entry format in
   .claude/knowledge-management.md
4. Update private/learnings-index.md with new entries (add to relevant
   service/topic)
5. Discard duplicates or findings that turned out to be incorrect
6. Check token budget: learnings.md should stay under 5,000 tokens total

## Part 2: Revise related files

For each promoted learning, check if it should propagate to other files:

- Should it become a permanent rule in .claude/rules/{service}/? If so, add
  it and mark the learning as "Graduated to: [path]"
- Does it affect an agent's "Before Starting Work" checklist?
- Does it invalidate anything in an existing spec or mental model?

For files touched during the current session:

- Check if any session insights should be captured but weren't
- Run `/process-doctor` to verify reference integrity after edits.
  This command does not duplicate that audit -- broken refs, stale
  `paths:` globs, and enforcement scaffolding drift are checked there.

Only write to spec-writer-owned files (rules, learnings,
knowledge-management.md). For owner-managed files (agents, commands, skills,
CLAUDE.md), flag findings but do not edit.

## Part 3: Report

After consolidation, report:

- Learnings promoted (with anchors)
- Drafts discarded (with reason)
- Files updated beyond learnings (rules, index, etc.)
- Current learnings.md token estimate
- Owner-managed files flagged for review (if any) -- suggest running the
  context-audit skill for full audit details

If any owner-managed or rule files were flagged, also run
`/process-doctor` to confirm the broader process graph is still
coherent (agent refs, command refs, rule paths, enforcement wiring).

Recommended cadence: weekly (pairs with /kata-check), end-of-session, or
when the `## Drafts` section has 3+ entries.
