'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { createAuthApi, ApiClientError } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const authApi = createAuthApi(apiClient);

export function useAuth() {
  const result = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: () => authApi.me(),
    retry: false,
    staleTime: 60_000,
  });

  // If auth/me returns 401, token is expired — clear cookie and redirect to login
  useEffect(() => {
    if (
      result.isError &&
      result.error instanceof ApiClientError &&
      result.error.status === 401 &&
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/login')
    ) {
      document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
      window.location.replace('/login');
    }
  }, [result.isError, result.error]);

  return result;
}
