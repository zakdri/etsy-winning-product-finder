import type { HealthResponse, ResearchRequest, ResearchResponse } from './types';

const DEFAULT_TIMEOUT_MS = 45_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '');
}

async function requestJson<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...init?.headers,
      },
      signal: controller.signal,
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        payload && typeof payload === 'object' && 'detail' in payload
          ? String(payload.detail)
          : `Request failed with status ${response.status}`;
      throw new ApiError(detail, response.status);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('The local API took too long to respond.');
    }
    throw new ApiError(
      error instanceof Error ? error.message : 'Unable to reach the local API.',
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

export function getHealth(baseUrl: string): Promise<HealthResponse> {
  return requestJson<HealthResponse>(baseUrl, '/api/v1/health');
}

export function runResearch(
  baseUrl: string,
  request: ResearchRequest,
): Promise<ResearchResponse> {
  return requestJson<ResearchResponse>(baseUrl, '/api/v1/research', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
