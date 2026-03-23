'use client';

import { useState, useMemo } from 'react';
import type { TimelineEvent } from '@keviq/domain-types';
import { buildInvocationDebugModel, getFailureLabel } from './invocation-debug-model';
import type { InvocationDebugModel, ToolTurnSummary } from './invocation-debug-model';

/**
 * InvocationDebugPanel — diagnosis surface for agent invocations.
 *
 * Extracts structured data from timeline events and presents:
 * 1. Terminal status + failure classification
 * 2. Summary metrics (turns, tools, latency, tokens)
 * 3. Turn-by-turn breakdown
 * 4. Human control intervention cues
 *
 * Collapsed by default — expanded on click.
 */

interface InvocationDebugPanelProps {
  events: TimelineEvent[];
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

const STATUS_COLORS: Record<string, string> = {
  completed: '#059669',
  failed: '#dc2626',
  timed_out: '#d97706',
  cancelled: '#6b7280',
};

const CATEGORY_COLORS: Record<string, string> = {
  tool_failure: '#dc2626',
  malformed_tools: '#dc2626',
  budget_exhausted: '#d97706',
  tool_rejected: '#7c3aed',
  tool_cancelled: '#6b7280',
  transport_error: '#dc2626',
  gateway_error: '#dc2626',
  guardrail_rejected: '#d97706',
  startup_error: '#dc2626',
  unknown: '#6b7280',
};

export function InvocationDebugPanel({ events }: InvocationDebugPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const model = useMemo(() => buildInvocationDebugModel(events), [events]);

  if (!model.hasData) return null;

  const statusColor = STATUS_COLORS[model.terminalStatus ?? ''] ?? '#6b7280';

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, marginBottom: 20 }}>
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', border: 'none', borderRadius: 8, cursor: 'pointer',
          backgroundColor: expanded ? '#f9fafb' : '#fff', textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>
            Invocation Debug
          </span>
          {model.terminalStatus && (
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
              backgroundColor: statusColor + '15', color: statusColor,
            }}>
              {model.terminalStatus.toUpperCase()}
            </span>
          )}
          {model.failureCategory && (
            <span style={{
              fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
              backgroundColor: (CATEGORY_COLORS[model.failureCategory] ?? '#6b7280') + '15',
              color: CATEGORY_COLORS[model.failureCategory] ?? '#6b7280',
            }}>
              {getFailureLabel(model.failureCategory)}
            </span>
          )}
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            {model.totalTurns} turn{model.totalTurns !== 1 ? 's' : ''}, {model.totalToolsCalled} tool{model.totalToolsCalled !== 1 ? 's' : ''}
          </span>
        </div>
        <span style={{ fontSize: 12, color: '#9ca3af' }}>{expanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid #f3f4f6' }}>
          {/* Error message */}
          {model.errorMessage && (
            <div style={{
              marginTop: 12, padding: 10, borderRadius: 6,
              backgroundColor: '#fef2f2', color: '#991b1b', fontSize: 13,
            }}>
              {model.errorMessage}
            </div>
          )}

          {/* Summary metrics */}
          <SummaryMetrics model={model} />

          {/* Turn breakdown */}
          {model.turns.length > 0 && <TurnBreakdown turns={model.turns} />}

          {/* Human control */}
          {model.humanControlEvents.length > 0 && <HumanControlCues events={model.humanControlEvents} />}
        </div>
      )}
    </div>
  );
}

function SummaryMetrics({ model }: { model: InvocationDebugModel }) {
  return (
    <div style={{
      marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
      gap: 8,
    }}>
      <MetricCard label="Turns" value={String(model.totalTurns)} />
      <MetricCard label="Tools called" value={String(model.totalToolsCalled)} />
      {model.totalToolFailures > 0 && (
        <MetricCard label="Tool failures" value={String(model.totalToolFailures)} color="#dc2626" />
      )}
      {model.totalModelLatencyMs !== null && (
        <MetricCard label="Model latency" value={formatMs(model.totalModelLatencyMs)} />
      )}
      {model.totalToolLatencyMs !== null && (
        <MetricCard label="Tool latency" value={formatMs(model.totalToolLatencyMs)} />
      )}
      {model.promptTokens !== null && (
        <MetricCard label="Prompt tokens" value={String(model.promptTokens)} />
      )}
      {model.completionTokens !== null && (
        <MetricCard label="Completion tokens" value={String(model.completionTokens)} />
      )}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      padding: 8, borderRadius: 6, backgroundColor: '#f9fafb',
      border: '1px solid #f3f4f6',
    }}>
      <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: color ?? '#111827' }}>{value}</div>
    </div>
  );
}

function TurnBreakdown({ turns }: { turns: ToolTurnSummary[] }) {
  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8, marginTop: 0 }}>
        Turn Breakdown
      </h4>
      <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Turn</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Tools</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Failed</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Duration</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Budget left</th>
          </tr>
        </thead>
        <tbody>
          {turns.map((t) => (
            <tr key={t.turnIndex} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: '4px 8px', color: '#374151' }}>{t.turnIndex + 1}</td>
              <td style={{ padding: '4px 8px', color: '#374151' }}>
                {t.toolCount}
                {t.tools.length > 0 && (
                  <span style={{ color: '#9ca3af', marginLeft: 4 }}>
                    ({t.tools.map((tool) => tool.name).join(', ')})
                  </span>
                )}
              </td>
              <td style={{ padding: '4px 8px', color: t.failureCount > 0 ? '#dc2626' : '#374151' }}>
                {t.failureCount}
              </td>
              <td style={{ padding: '4px 8px', color: '#374151' }}>
                {t.turnDurationMs !== null ? formatMs(t.turnDurationMs) : '-'}
              </td>
              <td style={{ padding: '4px 8px', color: '#374151' }}>
                {t.budgetRemainingMs !== null ? formatMs(t.budgetRemainingMs) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HumanControlCues({ events }: { events: Array<{ type: string; timestamp: string }> }) {
  const labels: Record<string, string> = {
    waiting_human: 'Paused for human approval',
    resumed: 'Resumed after approval',
    overridden: 'Operator override applied',
    cancelled: 'Cancelled by operator',
  };

  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8, marginTop: 0 }}>
        Human Interventions
      </h4>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {events.map((e, i) => (
          <li key={i} style={{
            fontSize: 12, padding: '4px 0', color: '#374151',
            display: 'flex', gap: 8,
          }}>
            <span style={{ color: '#7c3aed', fontWeight: 500 }}>{labels[e.type] ?? e.type}</span>
            <span style={{ color: '#9ca3af' }}>{new Date(e.timestamp).toLocaleTimeString()}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
