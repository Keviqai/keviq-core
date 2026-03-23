'use client';

import { useQuery } from '@tanstack/react-query';
import { createTelemetryApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const telemetryApi = createTelemetryApi(apiClient);

export function useTelemetryMetrics(service?: string) {
  return useQuery({
    queryKey: queryKeys.telemetry.metrics(service),
    queryFn: () => telemetryApi.getMetrics(service),
    staleTime: 30_000,
  });
}
