/**
 * Build a structured dashboard model from raw telemetry metric samples.
 *
 * Groups metrics by service, extracts key counters, and computes
 * derived values (average latency, error rate).
 */

import type { MetricSample } from '@keviq/api-client';

export interface ServiceHealth {
  service: string;
  requestCount: number;
  errorCount: number;
  avgLatencyMs: number | null;
  lastScraped: string | null;
}

export interface AgentRuntimeCounters {
  invocations: Record<string, number>;
  toolCalls: Record<string, number>;
  toolFailures: Record<string, number>;
  budgetExhaustions: number;
  humanGates: Record<string, number>;
}

export interface DashboardModel {
  services: ServiceHealth[];
  agentRuntime: AgentRuntimeCounters;
  lastScraped: string | null;
  totalSamples: number;
}

export function buildDashboardModel(samples: MetricSample[]): DashboardModel {
  const byService: Record<string, MetricSample[]> = {};
  let lastScraped: string | null = null;

  for (const s of samples) {
    if (!byService[s.source_service]) byService[s.source_service] = [];
    byService[s.source_service].push(s);
    if (s.scraped_at && (!lastScraped || s.scraped_at > lastScraped)) {
      lastScraped = s.scraped_at;
    }
  }

  const services: ServiceHealth[] = [];
  for (const [svc, metrics] of Object.entries(byService)) {
    const requestCount = sumByName(metrics, 'mona_http_requests_total');
    const errorCount = sumByName(metrics, 'mona_http_request_errors_total');
    const durationSum = sumByName(metrics, 'mona_http_request_duration_ms_sum');
    const durationCount = sumByName(metrics, 'mona_http_request_duration_ms_count');
    const avgLatency = durationCount > 0 ? Math.round(durationSum / durationCount) : null;
    const svcScraped = metrics[0]?.scraped_at ?? null;

    services.push({
      service: svc,
      requestCount,
      errorCount,
      avgLatencyMs: avgLatency,
      lastScraped: svcScraped,
    });
  }

  // Agent-runtime domain counters
  const arMetrics = byService['agent-runtime'] ?? [];
  const agentRuntime: AgentRuntimeCounters = {
    invocations: labelBreakdown(arMetrics, 'mona_agent_invocations_total', 'status'),
    toolCalls: labelBreakdown(arMetrics, 'mona_agent_tool_calls_total', 'status'),
    toolFailures: labelBreakdown(arMetrics, 'mona_agent_tool_failures_total', 'error_code'),
    budgetExhaustions: sumByName(arMetrics, 'mona_agent_budget_exhaustions_total'),
    humanGates: labelBreakdown(arMetrics, 'mona_agent_human_gates_total', 'decision'),
  };

  return { services, agentRuntime, lastScraped, totalSamples: samples.length };
}

function sumByName(samples: MetricSample[], name: string): number {
  return samples
    .filter((s) => s.metric_name === name)
    .reduce((sum, s) => sum + s.value, 0);
}

function labelBreakdown(
  samples: MetricSample[],
  name: string,
  labelKey: string,
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const s of samples) {
    if (s.metric_name !== name) continue;
    const key = s.labels[labelKey] ?? 'unknown';
    result[key] = (result[key] ?? 0) + s.value;
  }
  return result;
}
