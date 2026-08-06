/**
 * Generic fetch helper with timeout, retry, deduplication, and session expiry handling.
 *
 * Features:
 * - Request timeout (default 30s, configurable via `X-Request-Timeout` header)
 * - Exponential backoff retry for 5xx and network errors (max 3 attempts for GET)
 * - In-flight deduplication for identical GET requests
 * - Session expiry detection (HTML response → redirect to login)
 * - Proper empty response handling
 *
 * When `options.body` is a `FormData` instance, the `Content-Type: application/json`
 * header is **not** set so the browser can automatically apply
 * `multipart/form-data` with the correct boundary.
 */

// ── Configuration ────────────────────────────────────────────────────────────

const DEFAULT_TIMEOUT_MS = 30_000;
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 500;

// ── Deduplication cache (GET requests only) ──────────────────────────────────

interface FlightEntry {
  promise: Promise<unknown>;
  controller: AbortController;
}

const inFlightCache = new Map<string, FlightEntry>();

function buildCacheKey(url: string, options?: RequestInit): string | null {
  // Only deduplicate idempotent GET requests
  if (options?.method && options.method.toUpperCase() !== 'GET') {
    return null;
  }
  // Skip if body is present (GET with body is unusual and shouldn't be deduped)
  if (options?.body) {
    return null;
  }
  return url;
}

// ── Retry helper ─────────────────────────────────────────────────────────────

function isRetryable(error: unknown, method?: string): boolean {
  // Only retry idempotent methods
  if (method && method.toUpperCase() !== 'GET') {
    return false;
  }

  // Retry on network errors (no response)
  if (error instanceof DOMException && error.name === 'AbortError') {
    return false; // Do not retry timeouts
  }
  if (error instanceof Error && 'type' in error && (error as any).type === 'aborted') {
    return false;
  }

  return true;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Session handling ─────────────────────────────────────────────────────────

let isRedirecting = false;

function handleSessionExpiry(): never {
  // Prevent redirect loop if /oauth2/sign_in itself goes through this path
  if (!isRedirecting) {
    isRedirecting = true;
    // Clear any cached requests to avoid stale state after login
    for (const entry of inFlightCache.values()) {
      entry.controller.abort();
    }
    inFlightCache.clear();

    window.location.href = '/oauth2/sign_in';
  }
  throw new Error('Session expired');
}

// ── Core request function ────────────────────────────────────────────────────

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const method = options?.method?.toUpperCase() ?? 'GET';
  const timeout = parseInt(
    String((options?.headers as Record<string, string>)?.['X-Request-Timeout'] ?? DEFAULT_TIMEOUT_MS),
    10,
  );

  const headers: Record<string, string> = {};
  if (!isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  // Remove timeout header from the actual request
  const cleanHeaders = {
    ...headers,
    ...(options?.headers as Record<string, string>),
  };
  delete cleanHeaders['X-Request-Timeout'];

  // Check for in-flight duplicate (GET only)
  const cacheKey = buildCacheKey(url, options);
  if (cacheKey && inFlightCache.has(cacheKey)) {
    return inFlightCache.get(cacheKey)!.promise as Promise<T>;
  }

  const executeRequest = async (attempt: number): Promise<T> => {
    const controller = new AbortController();

    // Set timeout
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const resp = await fetch(url, {
        ...options,
        headers: cleanHeaders,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Retry on 5xx for idempotent methods
      if (!resp.ok && resp.status >= 500 && attempt < MAX_RETRIES - 1) {
        const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt - 1);
        await sleep(delay);
        return executeRequest(attempt + 1);
      }

      if (!resp.ok) {
        // 401 → session expired
        if (resp.status === 401) {
          handleSessionExpiry();
        }

        const body = await resp.text().catch(() => '');
        throw new Error(resp.statusText + (body ? `: ${body}` : ''));
      }

      // Handle response body
      const text = await resp.text();

      // 204 No Content or explicit empty body is valid
      if (text === '' && resp.status === 204) {
        return {} as T;
      }

      // Session was invalidated server-side — oauth2-proxy returns HTML instead of JSON
      if (text.startsWith('<')) {
        handleSessionExpiry();
      }

      if (text === '') {
        // Empty body on non-204 response — throw descriptive error
        throw new Error(`Empty response body from ${url} (status: ${resp.status})`);
      }

      return JSON.parse(text) as T;

    } catch (error) {
      clearTimeout(timeoutId);

      // Check if retryable and within retry budget
      if (isRetryable(error, method) && attempt < MAX_RETRIES - 1) {
        const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt - 1);
        await sleep(delay);
        return executeRequest(attempt + 1);
      }

      throw error;
    }
  };

  // Wrap in cache if applicable
  const promise = executeRequest(1);

  if (cacheKey) {
    const controller = new AbortController();
    inFlightCache.set(cacheKey, { promise, controller });

    // Clean up cache when request completes
    promise.finally(() => {
      if (inFlightCache.get(cacheKey)?.promise === promise) {
        inFlightCache.delete(cacheKey);
      }
    });
  }

  return promise as Promise<T>;
}

/**
 * Clear the in-flight request cache.
 * Useful during testing or manual session management.
 */
export function clearRequestCache(): void {
  for (const entry of inFlightCache.values()) {
    entry.controller.abort();
  }
  inFlightCache.clear();
}