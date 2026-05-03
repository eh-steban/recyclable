---
paths:
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
  - "frontend/**/*.spec.ts"
  - "frontend/**/*.spec.tsx"
  - "frontend/**/__tests__/**"
  - "frontend/tests/**"
---
# Frontend Testing Standards

## Philosophy

**Test behavior, not implementation.**

Ask: "What does the user see/do?" not "What does the code do internally?"

## Test Stack

- **Vitest** -- Test runner (configured in `vite.config.ts`)
- **React Testing Library** -- Component rendering and querying
- **Playwright** -- E2E browser automation (separate from unit tests)

## Setup Files

- `tests/setup.ts` -- Global test setup (cleanup after each test)
- `vite.config.ts` -- Vitest configuration in the `test` block

## Component Tests

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

describe('UserList', () => {
  it('displays user names', () => {
    render(<UserList users={mockUsers} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('filters users when status is selected', async () => {
    render(<UserList users={mockUsers} />);
    await userEvent.click(screen.getByRole('button', { name: /active/i }));
    expect(screen.queryByText('Inactive User')).not.toBeInTheDocument();
  });
});

// ❌ Bad - tests implementation details
test('calls setData on mount', () => {
  const setData = vi.fn();
  render(<DataComponent setData={setData} />);
  expect(setData).toHaveBeenCalled();
});
```

## Query Priority

Prefer queries in this order (most to least accessible):

1. `getByRole` -- accessible to everyone
2. `getByLabelText` -- form fields
3. `getByPlaceholderText` -- form fields without labels
4. `getByText` -- non-interactive content
5. `getByTestId` -- last resort

```tsx
// ✅ Preferred
screen.getByRole('button', { name: /submit/i })

// ⚠️ Use sparingly
screen.getByTestId('complex-canvas-element')
```

## Hook Tests

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { useUserData } from './useUserData';

test('fetches and returns user data', async () => {
  const { result } = renderHook(() => useUserData('42'));

  await waitFor(() => {
    expect(result.current.isLoading).toBe(false);
  });

  expect(result.current.user).toBeDefined();
  expect(result.current.user?.id).toBe('42');
});
```

## Mocking

- Mock API layer, not internal functions
- Use `vi.mock()` for module mocking
- Keep mocks close to tests or in `__mocks__/`

```tsx
import { vi } from 'vitest';

vi.mock('../api/users', () => ({
  fetchUser: vi.fn().mockResolvedValue({ id: 42, name: 'Alice' }),
}));

// Mock environment variables
vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
```

## Error State Testing

Every component with error state must test error display, retry
functionality, and recovery.

```tsx
describe('UserProfile error handling', () => {
  it('displays error message when fetch fails', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'));

    render(<UserProfile userId={42} />);

    await expect(
      screen.findByText(/unable to load|error|failed/i)
    ).resolves.toBeInTheDocument();
  });

  it('allows retry after error', async () => {
    vi.mocked(fetch)
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce(makeResponse(sampleUser));

    render(<UserProfile userId={42} />);
    await userEvent.click(await screen.findByRole('button', { name: /retry/i }));

    await expect(screen.findByText('Alice')).resolves.toBeInTheDocument();
  });
});
```

### Required Error Scenarios

| Scenario | Test Pattern |
| ---------- | -------------- |
| Network failure | Mock fetch rejection |
| 404 response | Mock 404 status |
| 500 response | Mock 500 status |
| Empty data | Render with empty arrays |

## Coverage Goals

Focus on critical user paths rather than arbitrary coverage numbers:

- Core CRUD flows (create, read, update, delete)
- Error states and loading states
- Form validation
- Accessibility

## Component Testing Hierarchy

1. Critical User Paths → Always test these
2. Error Handling      → Test failure scenarios
3. Edge Cases          → Empty data, extreme values
4. Accessibility       → Screen readers, keyboard nav
