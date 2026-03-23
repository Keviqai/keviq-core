'use client';

import { useMemo } from 'react';
import { useTelemetryMetrics } from '@keviq/server-state';
import { buildDashboardModel } from '@/modules/telemetry/dashboard-model';
import type { ServiceHealth, AgentRuntimeCounters } from '@/modules/telemetry/dashboard-model';

export default function HealthDashboardPage() {
  const { data, isLoading, isError, error } = useTelemetryMetrics();
  const model = useMemo(
    () => data?.items ? buildDashboardModel(data.items) : null,
    [data],
  );

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>System Health</h1>

      {isLoading && <p style={{ color: '#6b7280' }}>Loading metrics...</p>}
      {isError && (
        <div style={{ padding: 12, backgroundColor: '#fef2f2', borderRadius: 6, color: '#991b1b', fontSize: 13, marginBottom: 16 }}>
          {error instanceof Error ? error.message : 'Failed to load metrics. Run a scrape first.'}
        </div>
      )}

      {model && model.totalSamples === 0 && (
        <div style={{ padding: 16, border: '2px dashed #d1d5db', borderRadius: 8, color: '#6b7280', textAlign: 'center', marginBottom: 16 }}>
          No metrics data yet. Trigger a scrape from the telemetry service first.
        </div>
      )}

      {model && model.totalSamples > 0 && (
        <>
          {/* Freshness */}
          <p style={{ fontSize: 12, color: '#9ca3af', marginBottom: 16 }}>
            Last scraped: {model.lastScraped ? new Date(model.lastScraped).toLocaleString() : 'unknown'}
            {' '} ({model.totalSamples} samples)
          </p>

          {/* Service Health */}
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: '#374151' }}>Service Health</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 24 }}>
            {model.services.map((svc) => (
              <ServiceCard key={svc.service} health={svc} />
            ))}
          </div>

          {/* Agent Runtime */}
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: '#374151' }}>Agent Runtime</h2>
          <AgentRuntimeSection counters={model.agentRuntime} />
        </>
      )}
    </div>
  );
}

function ServiceCard({ health }: { health: ServiceHealth }) {
  const errorRate = health.requestCount > 0
    ? ((health.errorCount / health.requestCount) * 100).toFixed(1)
    : '0.0';
  const isHealthy = health.requestCount > 0 && parseFloat(errorRate) < 10;

  return (
    <div style={{
      border: '1px solid #e5e7eb', borderRadius: 8, padding: 14,
      backgroundColor: isHealthy ? '#f0fdf4' : health.requestCount === 0 ? '#f9fafb' : '#fef2f2',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>{health.service}</span>
        <span style={{
          fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
          backgroundColor: isHealthy ? '#05966915' : '#dc262615',
          color: isHealthy ? '#059669' : '#dc2626',
        }}>
          {isHealthy ? 'HEALTHY' : health.requestCount === 0 ? 'NO DATA' : 'DEGRADED'}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
        <div>
          <div style={{ color: '#6b7280' }}>Requests</div>
          <div style={{ fontWeight: 600, fontSize: 16 }}>{health.requestCount}</div>
        </div>
        <div>
          <div style={{ color: '#6b7280' }}>Errors</div>
          <div style={{ fontWeight: 600, fontSize: 16, color: health.errorCount > 0 ? '#dc2626' : '#111827' }}>
            {health.errorCount} ({errorRate}%)
          </div>
        </div>
        <div style={{ gridColumn: 'span 2' }}>
          <div style={{ color: '#6b7280' }}>Avg latency</div>
          <div style={{ fontWeight: 600 }}>{health.avgLatencyMs !== null ? `${health.avgLatencyMs}ms` : '-'}</div>
        </div>
      </div>
    </div>
  );
}

function AgentRuntimeSection({ counters }: { counters: AgentRuntimeCounters }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
      <CounterCard title="Invocations" data={counters.invocations} />
      <CounterCard title="Tool Calls" data={counters.toolCalls} />
      <CounterCard title="Tool Failures" data={counters.toolFailures} colorValues />
      <CounterCard title="Human Gates" data={counters.humanGates} />
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Budget Exhaustions</div>
        <div style={{ fontSize: 20, fontWeight: 600, color: counters.budgetExhaustions > 0 ? '#d97706' : '#111827' }}>
          {counters.budgetExhaustions}
        </div>
      </div>
    </div>
  );
}

function CounterCard({ title, data, colorValues }: { title: string; data: Record<string, number>; colorValues?: boolean }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>{title}</div>
      {entries.length === 0 ? (
        <span style={{ fontSize: 12, color: '#9ca3af' }}>No data</span>
      ) : (
        <div style={{ fontSize: 12 }}>
          {entries.map(([key, val]) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
              <span style={{ color: '#6b7280' }}>{key}</span>
              <span style={{ fontWeight: 600, color: colorValues && val > 0 ? '#dc2626' : '#111827' }}>{val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
