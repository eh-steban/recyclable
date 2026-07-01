---
# No auto-load. Load from `principles-hub.md` when a story is too big to ship.
---

# Splitting patterns

When a story fails the **Small** INVEST criterion, split it. Work through
Richard Lawrence's 9 patterns in order and use the first that fits.

**Pre-split check.** Confirm the story satisfies INVEST *except* for Small.
If it fails Valuable, it is a task masquerading as a story -- combine it
with other pieces until the whole is a real increment of value.

**Golden rule: always produce vertical slices.** Each resulting story still
touches every layer it needs and delivers observable value on its own. A
split that yields a layer ("just the API") is not a split, it is a
horizontal slice -- see `stories-and-invest.md`.

## 1. Workflow steps

**Cue:** a multi-step process ("user goes through X, then Y, then Z").

**Recipe:** each step becomes its own story. Ship the beginning and end
first -- build the simple end-to-end case, then layer in the middle steps.

- Before: publish a news story to the corporate website.
- After: publish directly -> with editor review -> with legal review ->
  view on staging -> publish from staging.

> Do NOT slice one step at a time from beginning to end. That is the most
> common mistake -- it produces horizontal slices with no end-to-end value
> until the last one.

## 2. Operations (CRUD)

**Cue:** the word "manage," or multiple CRUD operations.

**Recipe:** split by Create / Read / Update / Delete -- each operation is a
story.

- Before: manage my account.
- After: sign up -> edit settings -> cancel account.

## 3. Business rule variations

**Cue:** multiple equally complex business rules reaching the same outcome
differently.

**Recipe:** each rule variation is a separate story.

- Before: search for flights with flexible dates.
- After: "n days between x and y" -> "a weekend in December" -> "+/- n days
  of x and y".

## 4. Data variations

**Cue:** complexity comes from different forms, types, or granularities of
data.

**Recipe:** start with the simplest data model; add complexity
just-in-time. Localization is the classic case: build English first, add
Japanese and Arabic as separate stories.

- Start: search by county -> then by city / neighborhood -> then asymmetric
  origin / destination coverage.

## 5. Data entry methods (interface variations)

**Cue:** the UI is the main source of complexity, not the business logic.

**Recipe:** build the simplest possible UI first, then layer in richer
interaction.

- Before: search for flights between two destinations.
- After: simple date input -> fancy calendar UI.

These are not fully independent (the second builds on the first), but the
split still reduces risk and delivers earlier value.

## 6. Major effort first

**Cue:** splitting yields several stories, but most of the real work lives
in the infrastructure of the first one.

**Recipe:** separate the foundational story (the heavy lifting) from the
variations that become trivial once the infrastructure exists.

- Before: pay with VISA, MC, Diners Club, or AMEX.
- After: pay with one card type -> pay with all four (given one already
  implemented).

> This is the pattern that justifies our thick walking skeleton: Story 1 is
> the foundational effort; later stories are the trivial-once-infra-exists
> variations. See `stories-and-invest.md`.

## 7. Simple / complex (core + variations)

**Cue:** in planning, the story keeps growing as edge cases pile up ("what
about X?", "have you considered Y?").

**Recipe:** stop and ask "what is the simplest version?" Lock that as Story
1 with tight criteria. Break every variation into its own story.

- Core: search for flights between two destinations.
- Variations (each a story): max stops -> nearby airports -> flexible dates.

## 8. Defer non-functional requirements

**Cue:** a large share of effort is in performance, security, or scale --
not the core behavior.

**Recipe:** split into "make it work" and "make it [fast / secure /
scalable]".

- Story 1: search results (slow -- show a "searching" animation).
- Story 2: search results in under 5 seconds.

> Use carefully. Repeatedly shipping "make it work" and deprioritizing the
> NFR follow-up accumulates technical debt.

## 9. Break out a spike

**Cue:** the story is large not because it is complex, but because the
implementation is poorly understood -- you cannot estimate it at all.

**Recipe:** time-box an investigation to answer specific questions, then
implement.

- Spike: investigate credit-card processing options -- which provider, what
  integration complexity, what estimated size?
- Story: implement credit-card processing (given the spike is complete).

> **Spike is the last resort.** You almost always know enough to build
> something, and working code teaches more than research. Exhaust patterns
> 1-8 first.

## Evaluating a split

When multiple patterns apply, choose the split that:

1. **Reveals low-value work you can throw away.** Most value comes from a
   small share of functionality; the best split isolates the low-value 20%
   as a story you can deprioritize or delete.
2. **Produces equally-sized stories.** Four 2-point stories give more
   scheduling flexibility than a 5 and a 3. (This repo overrides equal
   sizing for the walking skeleton only -- see `stories-and-invest.md`.)

## The meta-pattern

When in doubt, apply this directly -- most of the 9 patterns are instances
of it:

1. **Find the core complexity.** What is most likely to surprise you? What
   depends on human behavior, a new integration, or external dependencies?
2. **Identify all the variations.** What is there many of? (Rules,
   personas, data types, interfaces, entities.)
3. **Reduce all variations to one.** Build a single, complete vertical
   slice through the complex part. That is Story 1. Everything else queues.
