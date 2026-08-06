/**
 * Shared API — barrel exports.
 *
 * @deprecated Import directly from domain-specific API modules.
 * This barrel exists for backward compatibility during migration.
 */

export { request } from "./client";
export {
  reservationsApi,
  guestSearchApi,
  modelsApi,
  settingsApi,
  performanceApi,
} from "./api";
export type {
  GuestSearchOptions,
  NameExtractionResponse,
  CropRegion,
} from "./api";