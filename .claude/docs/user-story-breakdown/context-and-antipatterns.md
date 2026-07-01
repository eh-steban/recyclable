---
# No auto-load. Load from `principles-hub.md` for splitting judgment and smells.
---

# Context and anti-patterns

## Cynefin-informed splitting

Not all work is equally knowable. Dave Snowden's Cynefin model changes how
you approach splitting -- match the effort to how predictable the work is.

- **Obvious** -- just build it. If too big, enumerate all the stories and
  do the most valuable first.
- **Complicated** -- enumerate stories; do the most valuable and/or most
  risky first.
- **Complex** -- do not try to find all stories. Find 1-2 that deliver
  value AND teach you something. Build and learn.
- **Chaotic** -- put out the fire. Story splitting is not the priority.

For complex work -- most high-value software -- enumerating every story
up front creates an *illusion of predictability*. The stories will change
as you learn. Be transparent about the uncertainty instead of pretending
the backlog is fixed.

## Anti-patterns

- **Splitting by architectural layer** ("build the API this phase") --
  produces no shippable value; fails Valuable and Independent.
- **Tasks dressed up as stories** ("As a developer, I want a DB schema") --
  no user value; combine them until there is a real story.
- **Skipping acceptance criteria** -- "done" becomes subjective; rework and
  disputes follow.
- **Spike as the first move** -- delays real learning; working code teaches
  more.
- **Shipping "make it work" without queuing the NFR** -- accumulates debt
  that is expensive to retrofit.
- **An epic in the increment** -- you will not finish it; break it down
  first.
