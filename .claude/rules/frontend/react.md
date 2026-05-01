---
paths:
  - "frontend/app/**/*.tsx"
  - "frontend/components/**/*.tsx"
  - "frontend/components/**/*.ts"
---
# React Patterns (Next.js App Router)

Default to **server components**. Reach for client components only for
browser APIs, event handlers, or stateful hooks. See
`frontend/CLAUDE.md` § Server vs Client Components.

## Component Organization

Feature-based organization, colocate related components, hooks, and types.

```text
components/
├── answer-card/
│   ├── index.ts                  # Public exports
│   ├── answer-card.tsx           # Server component (renders structure)
│   ├── feedback-buttons.tsx      # 'use client' (interactive)
│   └── types.ts
├── ask-box/
│   ├── ask-box.tsx               # 'use client' (form state, fetch)
│   └── types.ts
```

## Component Structure

```tsx
// components/answer-card/index.ts
export { AnswerCard } from './answer-card';

// components/answer-card/answer-card.tsx (server component)
import { FeedbackButtons } from './feedback-buttons';
import type { Answer } from '@/lib/domain/answer';

export function AnswerCard({ answer }: { answer: Answer }) {
  return (
    <article>
      {/* server-rendered structure */}
      <FeedbackButtons traceId={answer.traceId} />
    </article>
  );
}

// components/answer-card/feedback-buttons.tsx
'use client';
export function FeedbackButtons({ traceId }: { traceId: string }) {
  // event handlers, state
}
```

## State Management

| State Type | Approach |
|------------|----------|
| Server-fetched data | Fetch in server components; pass as props |
| URL state (filters, page) | `searchParams` in server components |
| UI-only client state | `useState` in a client component |
| Shared client state | React Context (sparingly) -- prefer URL state or server-rendered props |
| Mutations | Server Actions or POST to a route handler in `app/api/` |

## Data Fetching

- Server components: call `lib/db` / `lib/retrieval` directly. Cache with
  `unstable_cache` or rely on the route's render mode.
- Client components: fetch via `/api/...` route handlers. Never import
  server-only modules.
- Tag all DB-touching modules with `import 'server-only'` at the top.

## Props

- Define props interface in component file or colocated `types.ts`
- Use destructuring with defaults where appropriate
- Prefer composition over prop drilling

```tsx
// ✅ Good
interface UserCardProps {
  user: User;
  isSelected?: boolean;
  onSelect?: (userId: number) => void;
}

export const UserCard: React.FC<UserCardProps> = ({
  user,
  isSelected = false,
  onSelect,
}) => { ... };
```

## Hooks

- Prefix with `use`
- One concern per hook
- Return object for multiple values (easier to extend)

```tsx
// ✅ Good
export function useUserData(userId: string) {
  // ...
  return { user, isLoading, error, refetch };
}
```

## Styling (Tailwind)

- Use utility-first approach
- Group classes: layout → spacing → typography → colors → effects
- Extract repeated patterns to component variants

```tsx
// ✅ Good - logical grouping
<div className="flex items-center gap-4 p-4
  text-sm text-gray-700 bg-white rounded-lg shadow">
```
