'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useActivity, useTaskList, useMembers } from '@keviq/server-state';
import { workspacePath, taskDetailPath, runDetailPath } from '@keviq/routing';
import type { ActivityEvent } from '@keviq/domain-types';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle } from '@/modules/shared/ui-styles';
import { resolveDisplayName } from '@/modules/approval/member-display';

const EVENT_CATEGORIES = [
  { label: 'All', value: '' },
  { label: 'Tasks', value: 'task.' },
  { label: 'Runs', value: 'run.' },
  { label: 'Artifacts', value: 'artifact.' },
  { label: 'Approvals', value: 'approval.' },
  { label: 'Comments', value: 'comment.' },
  { label: 'Agent', value: 'agent_invocation.' },
  { label: 'Tools', value: 'sandbox.tool_execution.' },
];

const TIME_RANGES = [
  { label: 'All time', value: '' },
  { label: 'Today', value: 'today' },
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
];

function computeAfter(range: string): string | undefined {
  if (!range) return undefined;
  const now = new Date();
  if (range === 'today') now.setHours(0, 0, 0, 0);
  else if (range === '7d') now.setDate(now.getDate() - 7);
  else if (range === '30d') now.setDate(now.getDate() - 30);
  return now.toISOString();
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const EVENT_LABELS: Record<string, string> = {
  'task.submitted': 'Task submitted',
  'task.started': 'Task started',
  'task.completed': 'Task completed',
  'task.failed': 'Task failed',
  'task.cancelled': 'Task cancelled',
  'task.recovered': 'Task recovered',
  'task.retried': 'Task retried',
  'run.queued': 'Run queued',
  'run.started': 'Run started',
  'run.completing': 'Run finalizing',
  'run.completed': 'Run completed',
  'run.failed': 'Run failed',
  'run.cancelled': 'Run cancelled',
  'run.timed_out': 'Run timed out',
  'run.recovered': 'Run recovered',
  'step.started': 'Step started',
  'step.completed': 'Step completed',
  'step.failed': 'Step failed',
  'step.cancelled': 'Step cancelled',
  'step.recovered': 'Step recovered',
  'artifact.registered': 'Artifact created',
  'artifact.writing': 'Writing artifact',
  'artifact.ready': 'Artifact ready',
  'artifact.failed': 'Artifact failed',
  'artifact.lineage_recorded': 'Lineage recorded',
  'approval.requested': 'Approval requested',
  'approval.decided': 'Approval decided',
  'comment.created': 'Comment added',
  'tool_approval.requested': 'Tool approval needed',
  'tool_approval.decided': 'Tool approval decided',
  'agent_invocation.started': 'Agent started',
  'agent_invocation.completed': 'Agent completed',
  'agent_invocation.failed': 'Agent failed',
  'agent_invocation.waiting_human': 'Waiting for approval',
  'agent_invocation.waiting_tool': 'Running tools',
  'agent_invocation.turn_completed': 'Agent turn completed',
  'agent_invocation.resumed': 'Agent resumed',
  'agent_invocation.overridden': 'Agent overridden',
  'agent_invocation.cancelled': 'Agent cancelled',
  'agent_invocation.timed_out': 'Agent timed out',
  'sandbox.provisioned': 'Sandbox ready',
  'sandbox.terminated': 'Sandbox terminated',
  'sandbox.tool_execution.requested': 'Tool requested',
  'sandbox.tool_execution.succeeded': 'Tool succeeded',
  'sandbox.tool_execution.failed': 'Tool failed',
  'terminal.command.executed': 'Command executed',
};

function eventTypeLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType.replace(/[._]/g, ' ');
}

const CATEGORY_COLORS: Record<string, string> = {
  task: '#2563eb', run: '#7c3aed', artifact: '#059669',
  approval: '#d97706', comment: '#1d4ed8', agent_invocation: '#6366f1',
  tool_approval: '#f59e0b', sandbox: '#6b7280', step: '#9ca3af',
};

function eventColor(eventType: string): string {
  const prefix = eventType.split('.')[0];
  if (eventType.startsWith('agent_invocation.')) return CATEGORY_COLORS.agent_invocation;
  if (eventType.startsWith('tool_approval.')) return CATEGORY_COLORS.tool_approval;
  if (eventType.startsWith('sandbox.tool_execution.')) return CATEGORY_COLORS.sandbox;
  return CATEGORY_COLORS[prefix] ?? '#6b7280';
}

const ATTENTION_TYPES = new Set([
  'approval.requested', 'tool_approval.requested', 'agent_invocation.waiting_human',
  'task.failed', 'run.failed', 'run.timed_out', 'comment.created',
]);

// Low-signal system events hidden from "All" default view.
// Still visible when specific category filter is selected.
const LOW_SIGNAL_TYPES = new Set([
  'task.submitted', 'task.started',
  'step.started', 'step.completed', 'step.cancelled', 'step.recovered',
  'run.queued', 'run.started', 'run.completing',
  'agent_invocation.started', 'agent_invocation.turn_completed', 'agent_invocation.waiting_tool',
  'sandbox.provisioned', 'sandbox.terminated',
]);

export default function ActivityPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const [categoryFilter, setCategoryFilter] = useState('');
  const [timeRange, setTimeRange] = useState('');
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const after = useMemo(() => computeAfter(timeRange), [timeRange]);
  const { data: members } = useMembers(workspaceId);
  const { data: tasksData } = useTaskList(workspaceId);
  const taskTitleMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of tasksData?.items ?? []) map.set(t.task_id, t.title);
    return map;
  }, [tasksData]);
  const { data, isLoading, isError, error } = useActivity(workspaceId, {
    event_type: categoryFilter || undefined, after, limit, offset,
  });
  const rawEvents = data?.events ?? [];
  const attentionEvents = rawEvents.filter(e => ATTENTION_TYPES.has(e.event_type));
  const attentionCount = attentionEvents.length;
  const filteredEvents = attentionOnly
    ? attentionEvents
    : !categoryFilter
      ? rawEvents.filter(e => !LOW_SIGNAL_TYPES.has(e.event_type))
      : rawEvents;
  const events = filteredEvents;
  const totalCount = data?.total_count ?? 0;
  const hasMore = offset + limit < totalCount;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={workspacePath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>← Overview</Link>
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 16px' }}>
        Activity {totalCount > 0 && <span style={{ fontWeight: 400, fontSize: 16, color: '#9ca3af' }}>({totalCount})</span>}
      </h1>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setOffset(0); }} style={selectStyle}>
          {EVENT_CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <select value={timeRange} onChange={(e) => { setTimeRange(e.target.value); setOffset(0); }} style={selectStyle}>
          {TIME_RANGES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <button onClick={() => { setAttentionOnly(!attentionOnly); setOffset(0); }} style={{
          ...selectStyle, cursor: 'pointer',
          backgroundColor: attentionOnly ? '#fef3c7' : attentionCount > 0 ? '#fffbeb' : '#fff',
          borderColor: attentionOnly ? '#f59e0b' : attentionCount > 0 ? '#fde68a' : '#d1d5db',
          fontWeight: attentionOnly ? 600 : attentionCount > 0 ? 500 : 400,
        }}>
          Needs Attention{attentionCount > 0 ? ` (${attentionCount})` : ''}
        </button>
      </div>

      {isLoading ? <p style={{ color: '#6b7280' }}>Loading activity...</p>
       : isError ? (
        <div style={errorBoxStyle} role="alert">
          <p style={errorTitleStyle}>Failed to load activity</p>
          <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
        </div>
       ) : events.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#374151', marginBottom: 4 }}>No activity recorded yet</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>Events will appear here as tasks, runs, and artifacts are created.</p>
        </div>
       ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          {events.map((event) => (
            <ActivityRow key={event.event_id} event={event} workspaceId={workspaceId} members={members} taskTitleMap={taskTitleMap} />
          ))}
        </div>
       )}

      {(hasMore || offset > 0) && (
        <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'center' }}>
          {offset > 0 && <button onClick={() => setOffset(Math.max(0, offset - limit))} style={paginationBtnStyle}>← Newer</button>}
          {hasMore && <button onClick={() => setOffset(offset + limit)} style={paginationBtnStyle}>Older →</button>}
        </div>
      )}
    </div>
  );
}

function ActivityRow({ event, workspaceId, members, taskTitleMap }: {
  event: ActivityEvent; workspaceId: string;
  members: import('@keviq/domain-types').WorkspaceMember[] | undefined;
  taskTitleMap: Map<string, string>;
}) {
  const color = eventColor(event.event_type);
  const actorId = event.actor?.id || event.actor?.user_id;
  const rawActor = event.actor?.type || 'System';
  const actorName = actorId ? resolveDisplayName(actorId, members) : (rawActor === 'service' || rawActor === 'orchestrator' || rawActor === 'agent-runtime' ? 'system' : rawActor);
  const taskTitle = event.task_id ? taskTitleMap.get(event.task_id) : undefined;
  const truncTitle = taskTitle ? (taskTitle.length > 40 ? taskTitle.slice(0, 40) + '…' : taskTitle) : undefined;

  return (
    <div style={{ padding: '10px 14px', borderBottom: '1px solid #f3f4f6', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: color, flexShrink: 0, marginTop: 5 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#1f2937' }}>{eventTypeLabel(event.event_type)}</span>
          {truncTitle && (
            <Link href={taskDetailPath(workspaceId, event.task_id!)} style={{ fontSize: 12, color: '#6b7280', textDecoration: 'none' }}>
              on "{truncTitle}"
            </Link>
          )}
          <span style={{ fontSize: 12, color: '#9ca3af' }}>by {actorName}</span>
        </div>
        {event.event_type === 'comment.created' && typeof event.payload?.body_preview === 'string' && (
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2, fontStyle: 'italic' }}>
            "{event.payload.body_preview.slice(0, 100)}{event.payload.body_preview.length > 100 ? '…' : ''}"
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
        {event.task_id && !truncTitle && (
          <Link href={taskDetailPath(workspaceId, event.task_id)} style={{ fontSize: 11, color: '#2563eb', textDecoration: 'none' }}>task</Link>
        )}
        {event.run_id && (
          <Link href={runDetailPath(workspaceId, event.run_id)} style={{ fontSize: 11, color: '#7c3aed', textDecoration: 'none' }}>run</Link>
        )}
        <span style={{ fontSize: 11, color: '#9ca3af', whiteSpace: 'nowrap' }}>{formatRelativeTime(event.occurred_at)}</span>
      </div>
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: '6px 10px', fontSize: 13, borderRadius: 6, border: '1px solid #d1d5db', backgroundColor: '#fff', color: '#374151',
};
const paginationBtnStyle: React.CSSProperties = {
  padding: '6px 14px', fontSize: 13, borderRadius: 6, border: '1px solid #d1d5db', backgroundColor: '#fff', color: '#374151', cursor: 'pointer',
};
