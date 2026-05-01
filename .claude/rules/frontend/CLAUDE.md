---
paths:
  - "frontend/app/**/*.ts"
  - "frontend/app/**/*.tsx"
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
  - "frontend/lib/**/*.ts"
  - "frontend/components/**/*.tsx"
---

# Frontend Service

Next.js (App Router) + TypeScript web app. Serves SEO-crawlable
jurisdiction/material pages and the assistant UI. Owns the synchronous
user request path (Sonnet).

## Structure

<!-- markdownlint-disable MD013 -->
```text
frontend/
├── app/                                 # App Router routes (server components by default)
│   ├── layout.tsx
│   ├── page.tsx                         # Landing
│   ├── ask/
│   │   └── page.tsx                     # Assistant UI (server shell + client component)
│   ├── recycling/
│   │   └── [city]/
│   │       ├── page.tsx                 # SSG -- jurisdiction landing (revalidated on ingestion-apply)
│   │       └── [material]/
│   │           └── page.tsx             # SSG -- material page (revalidated on ingestion-apply)
│   └── api/
│       ├── ask/route.ts                 # Sonnet user path
│       ├── feedback/route.ts            # Answer feedback persistence
│       └── ingest/route.ts              # Operator-only (admin guarded)
│
├── components/                          # Feature-grouped components
│   ├── answer-card/
│   │   ├── index.ts
│   │   ├── answer-card.tsx              # 'use client' if interactive
│   │   └── types.ts
│   └── ask-box/
│       └── ...
│
├── lib/                                 # Pure utilities + clients
│   ├── db/                              # Postgres client + queries (server-only)
│   ├── llm/                             # Anthropic SDK wrapper, prompt versions, validators
│   ├── domain/                          # Type definitions mirroring backend domain
│   └── retrieval/                       # Material normalizer, rule retriever, source retriever
│
├── tests/                               # Mirrors app/ + components/ + lib/
│   ├── api/
│   ├── components/
│   ├── lib/
│   └── e2e/                             # Playwright
│
├── Dockerfile                           # Local prod-parity build (Vercel builds itself)
├── package.json
├── next.config.ts
└── tsconfig.json
```
<!-- markdownlint-enable MD013 -->

## Server vs client components

Default to **server components**. Reach for `'use client'` only when the
component needs:

- Browser APIs (`window`, `localStorage`, `navigator`).
- Event handlers (`onClick`, `onChange`) -- but a tiny client component
  nested inside a server component is preferable to flipping the whole
  tree.
- Hooks that touch state (`useState`, `useEffect`, `useReducer`).

Mark client components at the top of the file with `'use client'` and
keep them as small as possible. Server components can render client
components freely; the inverse requires passing server-rendered content as
`children`.

**Server-only modules** (DB clients, secret-bearing config, Anthropic SDK
calls) should be imported only from server components and route handlers.
Use `import 'server-only'` at the top of those modules to make accidental
client imports a build-time error.

## Route handlers (`app/api/.../route.ts`)

- Validate inputs at system boundaries with `zod`. Specifically:
  (a) `/api/ask` request bodies, and (b) parsed output from Sonnet (LLM
  structured responses). Do NOT use zod to validate DB query results (the
  backend's SQLAlchemy models and Alembic-managed schema guarantee row
  shape on write) or internal function boundaries (TS types are
  sufficient).
- Return typed JSON matching the contract spec in
  `private/specs/contracts/`.
- Wrap every Anthropic SDK call per `.claude/rules/llm/CLAUDE.md`
  (timeout, retry, prompt-version log, trace persistence).
- Set `runtime = 'nodejs'` (default) -- the edge runtime cannot use the
  `pg` driver.
- Persist an `AnswerTrace` for every `/api/ask` invocation, even on error
  paths.

## Rendering strategy

| Surface | Rendering | Why |
|---|---|---|
| `/` | Static | Fast landing |
| `/recycling/[city]` | SSG, event-driven revalidation (`revalidatePath` on ingestion-apply) | Crawlable, rarely changes |
| `/recycling/[city]/[material]` | SSG, event-driven revalidation (`revalidatePath` on ingestion-apply) | Crawlable per-material |
| `/ask` | Server shell + client `<AskBox/>` | Interactivity behind a fast first paint |
| `/api/ask` | Dynamic Node route handler | Runtime retrieval + Sonnet call |
| `/api/ingest` | Dynamic Node route handler, admin-guarded | Operator workflow |

Pages are pure SSG (`export const revalidate = false`). Trigger
`revalidatePath()` from the ingestion-apply server action after rule
writes -- event-driven only, no time-based revalidation, no polling. For
materials ingested after the initial build, set
`export const dynamicParams = true` so unknown params render dynamically
on first hit, then cache as static -- this avoids coupling ingestion to a
full Vercel rebuild.

## Layer dependency rules

```text
app/api/      -> lib/llm, lib/db, lib/retrieval, lib/domain
app/(routes)/ -> components/, lib/db, lib/domain
components/   -> lib/domain, lib/utils, other components/
lib/llm/      -> lib/domain
lib/db/       -> lib/domain
lib/retrieval -> lib/db, lib/llm, lib/domain
lib/domain/   -> nothing (pure type definitions)
```

| Layer | Can Import |
|-------|------------|
| `app/api/` | `lib/llm`, `lib/db`, `lib/retrieval`, `lib/domain`, `lib/utils` |
| `app/(routes)/` | `components/`, `lib/db` (server only), `lib/domain`, `lib/utils` |
| `components/` | `lib/domain`, `lib/utils`, other `components/` |
| `lib/llm/` | `lib/domain`, `lib/utils` |
| `lib/db/` | `lib/domain`, `lib/utils` |
| `lib/retrieval/` | `lib/db`, `lib/llm`, `lib/domain`, `lib/utils` |
| `lib/domain/` | Nothing (pure types) |
| `lib/utils/` | Nothing (pure utilities) |

## Commands

```bash
# Dev server (localhost:3000)
cd frontend && npm run dev

# Tests (Vitest)
npm test

# Tests with coverage
npm test -- --coverage

# Linting
npm run lint

# Type checking
npm run typecheck

# Production build (parity check; Vercel runs this in cloud)
npm run build && npm start

# E2E (Playwright)
npm run test:e2e
```

## Tech stack

- Next.js (App Router, RSC)
- TypeScript (strict mode)
- Tailwind CSS
- Anthropic SDK (`@anthropic-ai/sdk`) -- see `.claude/rules/llm/CLAUDE.md`
- `pg` (node-postgres) for DB access, server-only, with hand-written SQL.
  Do not introduce a parallel TS ORM (Drizzle, Prisma, Kysely, etc.) --
  the backend's SQLAlchemy schema (managed via Alembic) is the source of
  truth, and a second ORM in TS would create a duplicate schema that
  drifts.
- Vitest + React Testing Library
- Playwright for E2E
- `zod` for the two specific boundaries above (user input on `/api/ask`,
  parsed Sonnet output). Not for DB rows.

## Code quality

- Split components and route handlers at ~200-300 lines.
- Components with > 5-7 props are a refactor signal -- split or lift
  state.
- Route handlers with > 4-5 stages should extract orchestration into
  `lib/retrieval/` or similar.
- No "kitchen sink" props.
- Pass data and callbacks down via props -- avoid importing `lib/db` or
  `lib/llm` directly from components. Server components fetch and pass;
  client components consume.
- Never call Anthropic from a client component. Always go through
  `/api/ask`.
