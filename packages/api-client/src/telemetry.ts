import type { ApiClient } from './client';

export interface MetricSample {
  source_service: string;
  metric_name: string;
  labels: Record<string, string>;
  value: number;
  scraped_at: string | null;
}

export interface TelemetryApi {
  getMetrics: (service?: string) => Promise<{ items: MetricSample[]; count: number }>;
}

export function createTelemetryApi(client: ApiClient): TelemetryApi {
  return {
    getMetrics: (service) => {
      const params = service ? `?service=${encodeURIComponent(service)}` : '';
      return client.get(`/v1/telemetry/metrics${params}`);
    },
  };
}
