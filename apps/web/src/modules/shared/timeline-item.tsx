'use client';

import { useState } from 'react';
import type { TimelineEvent } from '@keviq/domain-types';
import { formatRelativeTime } from './format-utils';
import { getEventSummary, getActorLabel } from './event-summary';
import { getEventDetails, type DetailRow } from './event-detail';

const EVENT_LABELS: Record<string, string> = {
  'task.submitted': 'Task submitted', 'task.started': 'Task started',
  'task.completed': 'Task completed', 'task.failed': 'Task failed',
  'task.cancelled': 'Task cancelled', 'task.recovered': 'Task recovered',
  'run.queued': 'Run queued', 'run.started': 'Run started',
  'run.completing': 'Run completing', 'run.completed': 'Run completed',
  'run.failed': 'Run failed', 'run.cancelled': 'Run cancelled',
  'run.timed_out': 'Run timed out', 'run.recovered': 'Run recovered',
  'step.started': 'Step started', 'step.completed': 'Step completed',
  'step.failed': 'Step failed', 'step.cancelled': 'Step cancelled',
  'step.recovered': 'Step recovered',
  'artifact.registered': 'Artifact registered', 'artifact.writing': 'Artifact writing',
  'artifact.ready': 'Artifact ready', 'artifact.failed': 'Artifact failed',
  'artifact.lineage_recorded': 'Lineage recorded',
  'approval.requested': 'Approval requested', 'approval.decided': 'Approval decided',
  'sandbox.provisioned': 'Sandbox ready', 'sandbox.provision_failed': 'Sandbox failed',
  'sandbox.terminated': 'Sandbox terminated',
  'sandbox.tool_execution.requested': 'Tool requested',
  'sandbox.tool_execution.succeeded': 'Tool executed',
  'sandbox.tool_execution.failed': 'Tool failed',
  'terminal.command.executed': 'Terminal command',
};

const ERROR_EVENTS = new Set([
  'task.failed', 'task.cancelled', 'run.failed', 'run.cancelled', 'run.timed_out',
  'step.failed', 'step.cancelled', 'artifact.failed',
  'sandbox.provision_failed', 'sandbox.tool_execution.failed',
]);

const SUCCESS_EVENTS = new Set([
  'task.completed', 'run.completed', 'step.completed',
  'artifact.ready', 'sandbox.tool_execution.succeeded',
]);

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getEventStyle(eventType: string) {
  if (ERROR_EVENTS.has(eventType))
    return { color: '#991b1b', backgroundColor: '#fef2f2', dotColor: '#ef4444' };
  if (SUCCESS_EVENTS.has(eventType))
    return { color: '#065f46', backgroundColor: '#f0fdf4', dotColor: '#10b981' };
  return { color: '#374151', backgroundColor: 'transparent', dotColor: '#9ca3af' };
}

const badgeStyle: React.CSSProperties = {
  fontSize: 11, color: '#6b7280', backgroundColor: '#f3f4f6',
  padding: '1px 6px', borderRadius: 4, whiteSpace: 'nowrap',
};

export function TimelineItem({ event, onSelectExecution, memberMap }: { event: TimelineEvent; onSelectExecution?: (id: string) => void; memberMap?: Map<string, string> }) {
  const [expanded, setExpanded] = useState(false);
  const style = getEventStyle(event.event_type);
  const isError = ERROR_EVENTS.has(event.event_type);
  const summary = getEventSummary(event);
  const actor = getActorLabel(event.actor, memberMap);
  const details = getEventDetails(event);
  const hasDetail = details.length > 0;

  return (
    <div style={{ borderBottom: '1px solid #f3f4f6' }}>
      <div
        onClick={hasDetail ? () => setExpanded(!expanded) : undefined}
        style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          padding: '8px', marginLeft: -8, marginRight: -8,
          fontSize: 13, backgroundColor: style.backgroundColor,
          borderRadius: isError ? 4 : 0,
          cursor: hasDetail ? 'pointer' : 'default',
        }}
      >
        {/* Chevron or dot */}
        {hasDetail ? (
          <span style={{ fontSize: 10, color: '#9ca3af', flexShrink: 0, marginTop: 3, width: 10 }}>
            {expanded ? '▾' : '▸'}
          </span>
        ) : (
          <span style={{
            display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
            backgroundColor: style.dotColor, flexShrink: 0, marginTop: 5, marginLeft: 1.5,
          }} />
        )}

        <span style={{ color: '#6b7280', minWidth: 68, flexShrink: 0, fontSize: 12 }}>
          {formatTime(event.occurred_at)}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontWeight: isError ? 600 : 500, color: style.color }}>
            {EVENT_LABELS[event.event_type] ?? event.event_type}
          </span>
          {summary && (
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 1, lineHeight: 1.4 }}>
              {summary}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 4, flexShrink: 0, alignItems: 'center' }}>
          {actor && <span style={badgeStyle}>{actor}</span>}
          <span style={badgeStyle}>{event.emitted_by?.service ?? 'unknown'}</span>
        </div>

        <span style={{ color: '#9ca3af', fontSize: 11, flexShrink: 0, whiteSpace: 'nowrap' }}>
          {formatRelativeTime(event.occurred_at)}
        </span>
      </div>

      {/* Detail panel */}
      {expanded && hasDetail && (
        <DetailPanel rows={details} onSelectExecution={onSelectExecution} />
      )}
    </div>
  );
}

function DetailPanel({ rows, onSelectExecution }: { rows: DetailRow[]; onSelectExecution?: (id: string) => void }) {
  return (
    <div style={{
      padding: '8px 12px 8px 30px',
      backgroundColor: '#f9fafb',
      borderTop: '1px solid #f3f4f6',
      fontSize: 12,
    }}>
      {rows.map((row, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, marginBottom: i < rows.length - 1 ? 4 : 0 }}>
          <span style={{ color: '#6b7280', fontWeight: 500, minWidth: 70, flexShrink: 0 }}>
            {row.label}
          </span>
          {row.executionId && onSelectExecution ? (
            <button
              onClick={(e) => { e.stopPropagation(); onSelectExecution(row.executionId!); }}
              style={{
                color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer',
                padding: 0, fontSize: 12, textDecoration: 'underline',
              }}
            >
              {row.value}
            </button>
          ) : (
            <span style={{ color: '#111827', wordBreak: 'break-word' }}>
              {row.value}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
