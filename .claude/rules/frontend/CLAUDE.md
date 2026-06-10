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

Next.js (App Router) + TypeScript presentation layer. Serves
SEO-crawlable jurisdiction/material pages and the assistant UI.

**Does not connect to Postgres.** All data and LLM calls go through
the backend FastAPI HTTP service. The Sonnet user path executes in
the backend; the frontend renders its result.

**Does not own schema knowledge.** Row shapes, query construction,
and SQL live in the backend. The frontend consumes a TypeScript
client generated from the backend's OpenAPI spec (see
`.claude/rules/contracts.md`). When the schema changes, the frontend
re-runs codegen and the compiler catches type drift.

**Strategic DDD applies here** (Bounded Contexts, Ubiquitous
Language, translation at boundaries). Tactical patterns
(Aggregates, Repositories, Domain Events) are backend-only. See
`.claude/docs/ddd/principles-hub.md`; the shards are reference docs,
not auto-loaded rules -- open applicable ones on demand via the hub.

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
│   └── api/                             # BFF proxy routes (browser → Next.js → backend)
│       ├── ask/route.ts                 # Proxies POST /ask to backend
│       └── feedback/route.ts            # Proxies feedback to backend
│
├── components/                          # Feature-grouped components
│   ├── material-row.tsx                 # single-file leaf -- flat, no dir/barrel
│   ├── answer-card/                     # multi-file feature -- dir + index barrel
│   │   ├── index.ts
│   │   ├── answer-card.tsx              # 'use client' if interactive
│   │   └── types.ts
│   └── ask-box/
│       └── ...
│
├── lib/                                 # Pure utilities + clients
│   ├── api/                             # Backend HTTP client (server-only by default)
│   │   ├── client.ts                    # Generated OpenAPI client (do not hand-edit)
│   │   ├── types.ts                     # Generated wire types (do not hand-edit)
│   │   ├── citation.ts                  # Shared presentation value (Citation)
│   │   ├── jurisdiction.ts              # Jurisdiction-page types + translate + fetch
│   │   ├── material.ts                  # Material-page types + translate + fetch
│   │   └── index.ts                     # Thin public surface (re-exports)
│   └── utils/                           # Cross-cutting utilities
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

**Server-only modules** (server-side `lib/api/` calls that use the
backend's internal URL, secret-bearing config) should be imported only
from server components and route handlers. Use `import 'server-only'`
at the top of those modules to make accidental client imports a
build-time error.

**Browser-side data calls go through Next.js BFF route handlers, not
the backend directly.** Client components fetch from `/api/[route]`;
that handler proxies to the backend with the correct internal URL,
auth, and error mapping. The backend HTTP service is not exposed
directly to the browser. Server components and `generateStaticParams`
may call the backend directly (server-to-server, no CORS surface).

## Route handlers (`app/api/.../route.ts`) -- BFF proxies only

Frontend route handlers are thin proxies between the browser and the
backend HTTP API. They do **not** contain business logic, DB access, or
LLM calls.

- **Validate inputs.** Use `zod` to parse the browser's request body
  before forwarding. Reject malformed input with HTTP 400 before
  touching the backend.
- **Forward to the backend.** Use `lib/api/` (the generated client) to
  call the backend route. Pass through error responses with their
  status codes; do not swallow them.
- **Set `runtime = 'nodejs'`** (default). The Edge runtime is fine for
  pure proxies but not required.
- **No `AnswerAuditRecord` writes here.** Audit persistence is the
  backend's responsibility (the backend writes one row per `POST /ask`).
  The frontend route handler should pass the backend's `audit_record_id`
  back to the browser so feedback can correlate.
- **No retries here.** The backend handles upstream LLM retries. A
  failed backend call should propagate to the browser as-is.

## Rendering strategy

| Surface | Rendering | Why |
| --- | --- | --- |
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
app/api/      -> lib/api, lib/utils
app/(routes)/ -> components/, lib/api, lib/utils
components/   -> lib/api (types only), lib/utils, other components/
lib/api/      -> lib/utils  (generated client + thin wrappers)
lib/utils/    -> nothing
```

| Layer | Can Import |
| ------- | ------------ |
| `app/api/` (BFF route handlers) | `lib/api`, `lib/utils` |
| `app/(routes)/` (server components, SSG) | `components/`, `lib/api` (server side), `lib/utils` |
| `components/` | `lib/api` (types only), `lib/utils`, other `components/` |
| `lib/api/` | `lib/utils` |
| `lib/utils/` | Nothing |

There is no `lib/db/`, `lib/llm/`, `lib/retrieval/`, or `lib/domain/` in
this service. Those layers live in the backend. If you find yourself
wanting to add one of them here, the work belongs on the backend
instead.

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
- Backend HTTP client: generated from the backend's OpenAPI spec via
  `openapi-typescript` (types only) plus a thin hand-written fetch
  wrapper, OR a full client generator like `orval` if request shaping
  is repetitive. The generated artifact lives in `lib/api/` and is
  committed (not generated at deploy time). Re-run codegen whenever
  the backend's OpenAPI changes.
- **Do NOT add:** `pg`, `@anthropic-ai/sdk`, Prisma, Drizzle, Kysely,
  or any ORM/SQL/LLM-SDK package. All database and LLM access is the
  backend's responsibility. The frontend's only outbound dependency is
  the backend HTTP API.
- Vitest + React Testing Library
- Playwright for E2E
- Test-first discipline (red / green / refactor, captured red-state
  evidence): `.claude/docs/tdd.md`
- `zod` for the BFF route handlers' input validation (browser →
  Next.js boundary). The Next.js → backend boundary is typed by the
  generated client and does not need zod.

## Code quality

- Split components and route handlers at ~200-300 lines.
- Components with > 5-7 props are a refactor signal -- split or lift
  state.
- Route handlers with > 4-5 stages should extract orchestration into
  `lib/retrieval/` or similar.
- No "kitchen sink" props.
- Pass data and callbacks down via props. Server components fetch from
  `lib/api/` (server-side, direct to backend) and pass results into
  client components as props. Client components do not call `lib/api/`
  directly with the backend URL -- they go through Next.js BFF route
  handlers.
- Never call Anthropic from anywhere in the frontend. The Sonnet user
  path executes on the backend; the frontend renders the answer.
