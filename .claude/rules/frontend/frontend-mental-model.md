---
paths:
  - "frontend/**"
---

# Frontend Mental Model

Architecture constraints and load-bearing decisions for the Next.js
App Router frontend. This document describes how the frontend is
shaped and why -- not what specific files or APIs exist (those live
in code and in `.claude/rules/frontend/react.md`).

This is a stub. Fill in as constraints stabilize. Until then, treat
unwritten sections as "no committed constraint -- ask before
introducing one."

## Role of the frontend

The frontend serves two user surfaces from one Postgres knowledge base:

- **SEO-crawlable jurisdiction and material pages.** Server-rendered
  or statically generated. These are the durable, citation-anchored
  content surface that drives organic traffic.
- **Interactive `/ask` assistant.** A user asks a question; the route
  handler calls Sonnet synchronously, retrieves grounded rules from
  Postgres, and returns a cited answer or refusal.

Both surfaces share the same database and the same grounding contract.

## Architectural commitments

- **Sonnet on the user path.** Latency-sensitive, deterministic,
  retrieval-grounded. No agentic loops on the user path.
- **Citations are mandatory.** Every definitive claim renders with a
  source link. The UI surfaces "I cannot verify this" rather than
  hedging or paraphrasing.
- **SSG plus event-driven revalidation.** SEO pages are statically
  generated and revalidated when ingestion applies new rules. No
  user-perceived stale content for changed jurisdictions.
- **Server-side enforcement of grounding.** The route handler refuses
  to render an answer if grounding evidence is absent. Client-side
  validation is a UX layer, not a security layer.
- **Organize the Presentation Context by user-facing surface.**
  Presentation types, translation, and fetch helpers in `lib/api/`
  are grouped by the page or flow the user experiences -- the
  jurisdiction page, the material page, later the ask flow -- not
  by the backend's domain concepts and not by mechanical
  type-buckets (a single `types.ts` or `translate.ts` file).

  *Why:* a Presentation Context's reason-to-change is the UX, so
  the page is its natural cohesion axis (`ddd/modules.md`
  Principle 2). It keeps the frontend's Ubiquitous Language its
  own rather than echoing the backend's. It also mirrors the
  backend's already use-case-shaped Open Host Service resources
  (`ddd/integrating-bounded-contexts.md` Principle 4), yielding a
  clean 1:1 -- one resource -> one page module -> one route.

  *Guardrails:*
  - Genuinely shared presentation values get their own small
    module once a second consumer appears; do not duplicate --
    duplication drifts (`ddd/modules.md` Principle 5).
  - This organizes presentation *shapes*, not domain *decisions*.
    Grounding, verdict, and authority decisions stay in the
    backend; Smart-UI rejection still holds.

  This is strategic DDD -- Ubiquitous-Language-named, cohesive
  modules at the ACL boundary -- not tactical. No Entities,
  Aggregates, or Repositories in the frontend; those remain
  backend-only.

  *Cross-references:* `.claude/rules/architecture.md` §
  "Frontend: Smart-UI rejection" for the concrete `lib/api/`
  layout; `ddd/integrating-bounded-contexts.md` Principle 4
  (use-case-shaped OHS resources); `ddd/modules.md` Principle 2
  (cohesive concept, not mechanical bucket) and Principle 5
  (shared value module).

## Non-commitments (for now)

- Component library and styling choices beyond Tailwind defaults are
  not load-bearing yet.
- Auth model is not yet defined.
- Client-side state management beyond per-route concerns is not
  committed.

## Open questions

- How are draft or unpublished rules represented in the UI without
  leaking into SEO output?
- What is the offline / degraded-LLM behavior on `/ask`?
- How do we surface conflicts when two cited sources disagree?

When one of these is decided, promote the resolution into
`Architectural commitments` above and remove it from this list.
