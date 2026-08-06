/**
 * Shared — barrel exports for cross-cutting concerns.
 *
 * @deprecated Import directly from sub-path modules to enable tree-shaking:
 *   - `@/shared/api`
 *   - `@/shared/lib`
 *   - `@/shared/ui`
 *   - `@/shared/layout`
 *   - `@/shared/hooks`
 *   - `@/shared/types`
 *   - `@/shared/context`
 */

// API
export * from "./api";

// Utilities
export * from "./lib";

// UI Components
export * from "./ui";

// Layout
export * from "./layout";

// Hooks
export * from "./hooks";

// Types
export * from "./types";
export * from "./types/prompt";
export * from "./types/placeholder";

// Context (deprecated — migrate to Zustand stores)
export * from "./context/SettingsContext";
export * from "./context/ChainPagesContext";