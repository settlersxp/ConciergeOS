# Frontend Development Guide

Architecture rules and conventions for the ConciergeOS frontend.

## Architecture Rules

### Path Aliases

All imports must use the `@/` path alias (resolved to `./src/`):

```typescript
// ✅ Use path aliases
import { Button } from "@/shared/ui/Button";
import { modelsApi } from "@/shared/api/api";

// ❌ Never use deep relative imports
import { Button } from "../../../shared/ui/Button";
```

### Feature-Sliced Design

Each feature is self-contained in `features/<name>/` with its own page component, sub-components, and barrel export (`index.ts`). Features should not depend on each other — shared code belongs in `shared/`.

### State Management

| Layer | Use For | Location |
|-------|---------|----------|
| **React Context** | App-wide config (settings, chain pages) | `shared/context/` |
| **React Query** | Server state (API data, caching, mutations) | `shared/hooks/query/` |
| **Local State** | Component-internal UI state | Component files |

React Query defaults: 5min staleTime, no focus refetch, 1 retry.

### Shared Layer Organization

| Directory | Purpose |
|-----------|---------|
| `shared/api/` | HTTP client (`client.ts`) and API modules (`api.ts`) |
| `shared/hooks/query/` | React Query hooks (`useQuery`/`useMutation` wrappers) |
| `shared/lib/` | Pure utility functions (no React dependencies) |
| `shared/ui/` | Reusable UI primitives (Button, Card, Input, Toast…) |
| `shared/layout/` | App layout components (AppLayout, Header) |
| `shared/hooks/` | Shared custom hooks (useToast, useChainExecution…) |
| `shared/context/` | React Context providers (SettingsContext, ChainPagesContext) |
| `shared/types/` | TypeScript interfaces and types |

### API Client

All API calls go through `shared/api/client.ts` (`request<T>()`). The client provides:
- Request timeout (30s default, configurable via `X-Request-Timeout` header)
- Retry with exponential backoff (5xx/network errors, max 3 for GET)
- In-flight deduplication for identical GET requests
- Session expiry handling (401 or HTML response → redirect)
- Empty response error handling

### Barrels

Each module exports through an `index.ts` barrel. The root `shared/index.ts` is `@deprecated` — import from specific modules (e.g., `@/shared/ui` not `@/shared`).

## Development Workflow

### Adding a New Page

1. Create feature directory: `src/features/<name>/`
2. Add page component: `src/features/<name>/PageName.tsx` (default export)
3. Create barrel export: `src/features/<name>/index.ts`
4. Register route in `src/app/router/routeConfig.ts`
5. Add route constant in `src/app/router/routes.ts`
6. Add navigation item in `src/shared/layout/Header.tsx`

### Adding a New API Endpoint

1. Define types in `src/shared/types/` or feature's `types.ts`
2. Add function to appropriate API client in `src/shared/api/`
3. Create React Query hook in `src/shared/hooks/query/` for server state
4. Use in components via the query hook or API client

### Adding a Shared UI Component

1. Create component in `src/shared/ui/ComponentName.tsx`
2. Export from `src/shared/ui/index.ts`
3. Use Tailwind CSS for styling

### Adding Tests

1. Create `Component.test.tsx` or `hook.test.ts` alongside the source file
2. Use `@testing-library/react` for component tests
3. Mock `fetch` or API calls as needed

```typescript
// Example: hook test
import { renderHook, act } from '@testing-library/react';
import { useToast } from '@/shared/hooks/useToast';

describe('useToast', () => {
  it('shows and hides toast', () => {
    const { result } = renderHook(() => useToast());
    expect(result.current.toast.visible).toBe(false);

    act(() => {
      result.current.showToast('Hello', 'success');
    });
    expect(result.current.toast.visible).toBe(true);
    expect(result.current.toast.message).toBe('Hello');
  });
});
```

## Scripts

| Script | Command |
|--------|---------|
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Lint | `npm run lint` |
| Test (watch) | `npm run test` |
| Test (CI) | `npm run test:run` |
| Test coverage | `npm run test:coverage` |
| Bundle analyze | `ANALYZE=true npm run build` |