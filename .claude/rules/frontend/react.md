---
paths:
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
  - "frontend/src/**/**/*.ts"
  - "frontend/src/**/**/*.tsx"
---
# React Patterns

## Component Organization

Feature-based organization, not by file type. Colocate related components, hooks, and types.

```
src/components/
├── userProfile/
│   ├── index.ts                  # Public exports
│   ├── UserProfile.tsx
│   ├── UserAvatar.tsx
│   ├── hooks/
│   │   └── useUserProfile.ts
│   └── types.ts
├── orderHistory/
│   ├── OrderList.tsx
│   └── ...
```

## Component Structure

```tsx
// userProfile/index.ts
export { UserProfile } from './UserProfile';

// userProfile/UserProfile.tsx
import { useUserProfile } from './hooks/useUserProfile';

export const UserProfile: React.FC<Props> = ({ userId }) => {
  // Logic here
};
```

## State Management

| State Type | Approach |
|------------|----------|
| UI-only state | `useState` |
| Shared feature state | React Context |
| Server state | Fetch in hooks, cache as needed |

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
<div className="flex items-center gap-4 p-4 text-sm text-gray-700 bg-white rounded-lg shadow">
```
