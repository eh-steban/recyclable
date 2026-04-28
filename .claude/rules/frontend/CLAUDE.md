---
paths:
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
  - "frontend/src/**/**/*.ts"
  - "frontend/src/**/**/*.tsx"
---
# Frontend Service

React/TypeScript web application.

## Structure

```
frontend/
├── src/
│   ├── api/                          # API Clients
│   │   └── [resource].ts
│   │
│   ├── domain/                       # Domain Models (type definitions)
│   │   └── [resource].ts
│   │
│   ├── services/                     # Business Logic
│   │   └── [resource]/
│   │       └── index.ts
│   │
│   ├── components/                   # Feature-grouped Components
│   │   └── [feature]/
│   │       ├── index.ts              # Public exports
│   │       ├── [Feature].tsx
│   │       ├── hooks/
│   │       │   └── use[Feature].ts
│   │       └── types.ts
│   │
│   ├── pages/                        # Route-level Components
│   │   └── [Page].tsx
│   │
│   ├── utils/                        # Utilities
│   │   └── [util].ts
│   │
│   ├── App.tsx
│   └── index.tsx
│
├── tests/                            # Mirrors src/ structure
│   ├── setup.ts
│   ├── api/
│   ├── domain/
│   ├── services/
│   ├── components/
│   └── pages/
│
├── Dockerfile
├── package.json
└── vite.config.ts
```

## Layer Dependency Rules

```
┌─────────────────────────────────────────────────────────────┐
│                        pages/                               │
│                          ↓                                  │
│                     components/                             │
│                    ↓     ↓    ↓                             │
│               hooks/   api/  services/                      │
│                    ↓     ↓    ↓                             │
│                       domain/                               │
│                                                             │
│              utils/ ← (available to all)                    │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Can Import |
|-------|------------|
| `pages/` | `components/`, `hooks/`, `api/`, `domain/`, `services/`, `utils/` |
| `components/` | `hooks/`, `domain/`, `utils/`, other `components/` |
| `hooks/` | `api/`, `domain/`, `services/`, `utils/` |
| `api/` | `domain/`, `utils/` |
| `services/` | `domain/`, `utils/` |
| `domain/` | Nothing (pure type definitions) |
| `utils/` | Nothing (pure utilities) |

## Commands

```bash
# Dev server
cd frontend && npm run dev

# Tests
npm test

# Tests with coverage
npm test -- --coverage

# Linting
npm run lint

# Type checking
npm run typecheck

# Build
npm run build
```

## Tech Stack

- React
- TypeScript (strict mode)
- Vite
- Tailwind CSS
- Vitest

## Code Quality

- Split components and hooks at ~200-300 lines
- Components with >5-7 props are a refactor signal -- consider splitting or lifting state to context
- No "kitchen sink" props: each component interface should cover exactly what it needs, nothing more
- Pass data and callbacks down via props or context -- avoid importing services directly inside components
