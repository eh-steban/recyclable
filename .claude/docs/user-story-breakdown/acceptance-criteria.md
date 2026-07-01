---
# No auto-load. Load from `principles-hub.md` when defining "done" for a story.
---

# Acceptance criteria

Acceptance criteria are the confirmation that a story is done -- the "T" in
INVEST. Without them a story becomes a vague aspiration that can never be
closed.

## The 3 C's

- **Card** -- the written story.
- **Conversation** -- the discussion that builds shared understanding of
  how it will be implemented.
- **Confirmation** -- the acceptance criteria that define when it is done.

## Given-When-Then

Write acceptance criteria in the Given-When-Then format (Dan North, 2003,
from Behavior-Driven Development). It structures each criterion into a
precondition, an action, and an observable outcome:

```text
Given [a system state or precondition]
When  [a user takes an action]
Then  [an observable outcome occurs]
```

Example:

```text
Given a user is logged out
When they submit valid credentials
Then they are redirected to the dashboard and see a welcome message
```

Multiple scenarios per story are expected -- cover the happy path, edge
cases, and error conditions as separate scenarios. Each scenario is one
observable behavior, not a bundle.

## How criteria become checks in this repo

Given-When-Then maps directly onto how a phase (story) is verified:

- Each scenario becomes a **behavior check** in the phase checkpoint, and
  the primary scenario is the phase's **increment demo** (run the CLI /
  walk the UI / hit the endpoint the story makes usable).
- A scenario that describes a definite input/output pair is a candidate for
  an automated test; write it per `../tdd.md` (the "Then" is the assertion,
  the "Given" is the fixture, the "When" is the call under test).
- A story with no writable Given-When-Then scenario is not Testable -- it
  fails INVEST. Sharpen it before building.

Keep the criteria observable. "The system is fast" is not a criterion;
"search returns in under 5 seconds" is. If you cannot phrase the "Then" as
something a person or a test can observe, it is not done-able.
