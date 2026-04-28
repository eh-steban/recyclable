---
paths:
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
  - "frontend/src/**/**/*.ts"
  - "frontend/src/**/**/*.tsx"
---
# TypeScript Standards

## General

- TypeScript strict mode enabled
- Avoid `any` -- use `unknown` with type guards
- Type all props, state, and API responses
- Infer types from API schemas where possible

## Interface vs Type

**Prefer `interface` over `type`** unless using an interface is overkill.

Reasons:
- Better error messages
- More flexible when extending
- Declaration merging when needed

```typescript
// ✅ Preferred - interface for object shapes
interface User {
  id: number;
  name: string;
  email: string;
}

interface Order {
  id: number;
  userId: number;
  items: OrderItem[];
  total: number;
}

// ✅ Extend with interface
interface DetailedUser extends User {
  preferences: UserPreferences;
}

// ✅ Type is fine for unions, primitives, utilities
type Status = 'pending' | 'active' | 'cancelled';
type UserId = number;
type UserMap = Record<UserId, User>;

// ✅ Type is fine for simple function signatures
type PriceCalculator = (quantity: number, unitPrice: number) => number;
```

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files (general) | camelCase | `userService.ts`, `useUserData.ts` |
| Files (components) | PascalCase | `UserCard.tsx`, `OrderList.tsx` |
| Interfaces | PascalCase | `User`, `OrderItem` |
| Types | PascalCase | `Status`, `UserId` |
| Constants | UPPER_SNAKE_CASE | `API_BASE_URL`, `MAX_RETRY_COUNT` |

## Null Handling

- Prefer `undefined` over `null` for optional values
- Use optional chaining (`?.`) and nullish coalescing (`??`)
- Be explicit about nullable types

```typescript
// ✅ Good
interface UserState {
  currentPage?: number;      // Optional, may be undefined
  selectedUser: User | null; // Explicitly nullable
}

// ✅ Good - explicit handling
const userName = users.find(u => u.id === id)?.name ?? 'Unknown';
```

## Generics

Use generics for reusable utilities, but don't over-engineer:

```typescript
// ✅ Good - useful generic
function groupBy<T, K extends string | number>(
  items: T[],
  keyFn: (item: T) => K
): Record<K, T[]> { ... }

// ❌ Overkill for simple cases
function getUserName<T extends { name: string }>(user: T): string {
  return user.name;  // Just use User type directly
}
```
