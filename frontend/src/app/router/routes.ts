/** Route path constants */
export const ROUTES = {
  HOME: '/',
  PERFORMANCE_TESTING: '/performance-testing',
  PROMPTS: '/prompts',
  PROMPT_GROUPS: '/prompt-groups',
  PERFORMANCE_DASHBOARD: '/performance-dashboard',
  SETTINGS: '/settings',
  PROMPT_CHAINS: '/prompt-chains',
} as const;

/** Get display name for a route */
export function getRouteName(path: string): string {
  const names: Record<string, string> = {
    [ROUTES.HOME]: 'Reservations',
    [ROUTES.PERFORMANCE_TESTING]: 'Performance Testing',
    [ROUTES.PROMPTS]: 'Prompt Management',
    [ROUTES.PROMPT_GROUPS]: 'Prompt Groups',
    [ROUTES.PERFORMANCE_DASHBOARD]: 'Performance Dashboard',
    [ROUTES.SETTINGS]: 'Settings',
  };
  return names[path] ?? path;
}