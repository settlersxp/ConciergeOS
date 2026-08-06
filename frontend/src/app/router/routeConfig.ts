import { lazy } from "react";
import { ROUTES } from "./routes";

/**
 * Lazy-loaded page components. Importing from feature barrel exports
 * enforces feature encapsulation — the router never reaches into a
 * feature's internal file structure.
 */
const featurePages = {
  Reservations: lazy(() => import("@/features/reservations")),
  PerformanceTesting: lazy(() => import("@/features/performance-testing")),
  PromptManagement: lazy(() => import("@/features/prompt-management")),
  PromptGroups: lazy(() => import("@/features/prompt-groups")),
  PerformanceDashboard: lazy(() => import("@/features/performance-dashboard")),
  Settings: lazy(() => import("@/features/settings")),
  PromptChainPage: lazy(() => import("@/features/prompt-chains")),
};

/**
 * Route configuration: maps paths to lazy-loaded page components.
 * Adding a new static route = one line here + one entry in ROUTES.
 */
export const staticRoutes = [
  { path: ROUTES.HOME, component: featurePages.Reservations },
  { path: ROUTES.PERFORMANCE_TESTING, component: featurePages.PerformanceTesting },
  { path: ROUTES.PROMPTS, component: featurePages.PromptManagement },
  { path: ROUTES.PROMPT_GROUPS, component: featurePages.PromptGroups },
  { path: ROUTES.PERFORMANCE_DASHBOARD, component: featurePages.PerformanceDashboard },
  { path: ROUTES.SETTINGS, component: featurePages.Settings },
] as const;

export { featurePages };