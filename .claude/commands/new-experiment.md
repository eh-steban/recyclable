Create a new experiment directory in private/product/experiments/.

Use the spec-writer agent. Apply `.claude/rules/experiment-style.md`
throughout -- kata steps are outcome-shaped, not implementation-shaped.

1. Find the highest-numbered existing experiment directory.
2. Create the next number (e.g., if 02 exists, create 03).
3. Ask the user for:
   - Experiment name (short, descriptive, kebab-case suffix)
   - Which option from `private/product/strategy/current-options.md`
     this tests (or "new option")
   - Hypothesis (the falsifiable claim)
   - Target condition (specific and measurable -- predicates a
     reviewer can evaluate without reading source)
   - Current condition (quantified baseline)
   - First obstacle to address
   - First step (outcome at end of week 1, plus pass condition)
   - Experiment type
     (concierge | concept-test | wizard-of-oz | build-to-learn)
   - Cost of Delay assessment (urgency + value)
4. Scaffold `kata.md` from `private/templates/katas/kata.md`. Fill in
   header, hypothesis, target condition, current condition,
   definition of done, first obstacle, and Step 1. Leave Step 2 and
   Step 3 as `[deferred to design pass]` outcomes -- do not invent
   them at scaffold time.
5. Create empty `learnings.md` in the same directory.
6. Update `private/product/strategy/current-options.md` if this is a
   new option.

Before saving the kata: verify no Step contains a framework name, a
source-tree path, an implementation verb without an outcome, or a
field-level contract. If any of those appear, rewrite as outcome.

Remind the user: "Steps should take no more than one week. What's the
smallest thing we can do to learn whether this hypothesis is true?"
