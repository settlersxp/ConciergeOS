import type {
  AppSettings,
  Batch,
  GuestDetail,
  GuestSearchResponse,
  ModelsApiResponse,
  PerformanceTestRequest,
  ReservationsSummary,
  ShiftResponse,
  TestGuest,
  TestResult,
} from '../types';

/** Generic fetch helper that parses JSON responses */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(resp.statusText + (body ? `: ${body}` : ''));
  }
  // Some endpoints may return an empty body (e.g. 204)
  const text = await resp.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

// ── Reservations ────────────────────────────────────────────────────────────

export const reservationsApi = {
  getSummary: () => request<ReservationsSummary>('/api/reservations'),

  shift: (days = 1) =>
    request<ShiftResponse>('/api/reservations/shift', {
      method: 'POST',
      body: JSON.stringify({ days }),
    }),
};

// ── Guest Search ────────────────────────────────────────────────────────────

export const guestSearchApi = {
  search: (customerName: string) =>
    request<GuestSearchResponse>('/api/guest-search', {
      method: 'POST',
      body: JSON.stringify({ customer_name: customerName }),
    }),
};

// ── Settings ────────────────────────────────────────────────────────────────

export const settingsApi = {
  get: () => request<AppSettings>('/api/settings'),

  update: (settings: AppSettings) =>
    request<Record<string, unknown>>('/api/settings', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),

  getModels: () => request<ModelsApiResponse>('/api/models'),
};

// ── Performance Testing ─────────────────────────────────────────────────────

export const performanceApi = {
  runTest: (payload: PerformanceTestRequest) =>
    request<Record<string, unknown>>('/api/performance-testing', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getResults: () => request<TestResult[]>('/api/performance-testing/results'),

  getAllResults: () => request<TestResult[]>('/api/performance-testing/all-results'),

  getBatches: () => request<Batch[]>('/api/performance-testing/batches'),

  getResultsByBatch: (batchUuid: string) => {
    if (typeof batchUuid !== 'string' || !batchUuid.trim()) {
      throw new Error(`Invalid batch_uuid: expected a non-empty string, got ${batchUuid}`);
    }
    return request<TestResult[]>(`/api/performance-testing/results-by-batch?batch_uuid=${encodeURIComponent(batchUuid.trim())}`);
  },

  updateValidResponse: (resultId: number, validResponse: boolean) =>
    request<Record<string, unknown>>(`/api/performance-testing/result/${resultId}`, {
      method: 'PATCH',
      body: JSON.stringify({ valid_response: validResponse }),
    }),

  deleteBatch: (batchUuid: string) =>
    request<Record<string, unknown>>(`/api/performance-testing/batch/${batchUuid}`, {
      method: 'DELETE',
    }),

  setupGuests: () =>
    request<{ ok: boolean; guests: TestGuest[]; total: number }>('/api/performance-testing/setup-guests', {
      method: 'POST',
    }),

  generateXml: () =>
    request<{ ok: boolean; path?: string; size_bytes?: number; error?: string }>('/api/performance-testing/generate-xml', {
      method: 'POST',
    }),

  generateAll: () =>
    request<{ ok: boolean; files?: Record<string, unknown>; error?: string }>('/api/performance-testing/generate-all', {
      method: 'POST',
    }),

  getTestGuests: () => request<TestGuest[]>('/api/performance-testing/test-guests'),

  getGuestDetail: (guestId: number) =>
    request<GuestDetail>(`/api/performance-testing/guest/${guestId}`),
};
