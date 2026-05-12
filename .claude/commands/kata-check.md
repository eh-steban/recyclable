Use the spec-writer agent for this command. Active experiment = the kata.md in
private/product/experiments/ whose header contains `Status: active-experiment`
or `Status: discovery`.

Read the active experiment in private/product/experiments/ (find the one with
`Status: active-experiment` or `Status: discovery`) and answer the five
Coaching Kata questions:

1. What is the target condition?
2. What is the current condition now?
3. What obstacles do you think are preventing you from reaching the target
   condition? Which ONE are you addressing now?
4. What is your next step? What do you expect?
5. When can we go and see what we have learned from taking that step?

Then assess:

- Are we still within our one-week time-box?
- Is the current step still the right next action?
- Should we update the experiment file based on what we've learned?
- **Has the kata drifted from outcome-shape?** Per
  `.claude/rules/experiment-style.md`, steps should describe what's
  true at end of week, not what we built (no framework names, no
  source-tree paths, no `Implement X` verbs without an outcome). If
  drift has appeared, propose rewriting the affected steps.

If updates are needed, propose specific edits to the kata.md file.
