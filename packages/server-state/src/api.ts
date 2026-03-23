import { createApiClient } from '@keviq/api-client';

const API_URL = typeof window !== 'undefined'
  ? (window as unknown as Record<string, unknown>).__MONA_API_URL as string ?? ''
  : '';

export const apiClient = createApiClient(API_URL);
