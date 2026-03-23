'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { useTask, useRunsByTask, useTaskTimeline, useArtifactsByRun, useArtifactPreview, useMembers } from '@keviq/server-state';
import { useEventStream } from '@keviq/live-state';
import { hasCapability } from '@keviq/permissions';
import { tasksPath, taskEditPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { TimelineFeed, EMPTY_TIMELINE_EVENTS } from '@/modules/shared/timeline-feed';
import { buildMemberMap } from '@/modules/shared/member-map';
import { ConnectionStatusBadge } from '@/modules/shared/connection-status';
import { useEventInvalidation } from '@/modules/shared/use-event-invalidation';
import { formatRelativeTime } from '@/modules/shared/format-utils';
import { TaskCommentSection } from '@/modules/collaboration/task-comment-section';
import { TaskBriefSummary } from './_components/task-brief-summary';
import { TaskAgentInfo } from './_components/task-agent-info';
import { TaskActions } from './_components/task-actions';
import { TaskResultBanner } from './_components/task-result-banner';

export default function TaskDetailPage() {
  const params = useParams<{ workspaceId: string; taskId: string }>();
  const { workspaceId, taskId } = params;
  const { data: task, isLoading, isError, error } = useTask(taskId);
  const { data: runsData } = useRunsByTask(workspaceId, taskId);
  const { data: timelineData } = useTaskTimeline(taskId, workspaceId);
  const { data: members } = useMembers(workspaceId);
  const memberMap = useMemo(() => buildMemberMap(members), [members]);
  const onInvalidate = useEventInvalidation();
  const { status: connectionStatus } = useEventStream({
    workspaceId,
    scope: { type: 'workspace' },
    onInvalidate,
  });

  // Fetch artifacts for the latest run (result-first)
  const latestRun = runsData?.items?.[0] ?? null;
  const latestRunId = latestRun?.run_id ?? '';
  const { data: runArtifacts } = useArtifactsByRun(workspaceId, latestRunId);
  const latestArtifact = runArtifacts?.items?.[0] ?? null;
  const latestArtifactId = latestArtifact?.id ?? '';
  const { data: previewData } = useArtifactPreview(workspaceId, latestArtifactId);

  if (isLoading) {
    return <p style={{ color: '#6b7280' }}>Loading task...</p>;
  }

  if (isError || !task) {
    return (
      <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
        <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load task</p>
        <p style={{ color: '#b91c1c', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'Task not found or an unexpected error occurred.'}
        </p>
        <Link href={tasksPath(workspaceId)} style={{ color: '#1d4ed8', fontSize: 13 }}>
          Back to tasks
        </Link>
      </div>
    );
  }

  const canCancel = hasCapability(task._capabilities, 'can_cancel');
  const canRetry = hasCapability(task._capabilities, 'can_retry');
  const canViewRun = hasCapability(task._capabilities, 'can_view_run');
  const previewSnippet = previewData?.content?.slice(0, 250) ?? '';

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={tasksPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          ← Tasks
        </Link>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, marginBottom: 6 }}>{task.title}</h1>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <StatusBadge status={task.task_status} />
            <span style={{ fontSize: 13, color: '#6b7280' }}>{task.task_type}</span>
            <span style={{ fontSize: 13, color: '#9ca3af' }}>Updated {formatRelativeTime(task.updated_at)}</span>
            {latestRun && ['completed', 'failed'].includes(latestRun.run_status) && (
              <span style={{ fontSize: 12, color: '#6d28d9', backgroundColor: '#f5f3ff', padding: '2px 8px', borderRadius: 4 }}>
                {latestArtifact ? 'output available' : latestRun.run_status === 'completed' ? 'completed by AI' : 'agent run failed'}
              </span>
            )}
          </div>
        </div>
        {task.task_status === 'draft' && (
          <Link href={taskEditPath(workspaceId, taskId)} style={{
            padding: '6px 16px', backgroundColor: '#2563eb', color: '#fff',
            borderRadius: 6, fontSize: 13, fontWeight: 600, textDecoration: 'none',
          }}>
            Edit Brief
          </Link>
        )}
        <TaskActions taskId={taskId} workspaceId={workspaceId} canCancel={canCancel} canRetry={canRetry} />
      </div>

      {/* P7-S1: State-aware result banner */}
      {task.task_status !== 'draft' && (
        <TaskResultBanner
          taskStatus={task.task_status}
          workspaceId={workspaceId}
          latestRun={latestRun}
          latestArtifact={latestArtifact}
          previewSnippet={previewSnippet}
          canViewRun={canViewRun}
          canRetry={canRetry}
        />
      )}

      {/* Brief + Agent */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
        <TaskBriefSummary task={task} />
        <TaskAgentInfo agentTemplateId={task.agent_template_id} riskLevel={task.risk_level} />
      </div>

      {/* Timeline — collapsed by default for non-technical users */}
      {task.task_status !== 'draft' && (
        <TaskTimelineSection
          events={timelineData?.events ?? EMPTY_TIMELINE_EVENTS}
          memberMap={memberMap}
          connectionStatus={connectionStatus}
        />
      )}

      {/* Comments */}
      <TaskCommentSection workspaceId={workspaceId} taskId={taskId} members={members} />
    </div>
  );
}

function TaskTimelineSection({ events, memberMap, connectionStatus }: {
  events: import('@keviq/domain-types').TimelineEvent[];
  memberMap?: Map<string, string>;
  connectionStatus: import('@keviq/live-state').ConnectionStatus;
}) {
  const [expanded, setExpanded] = useState(false);
  const eventCount = events.length;

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            fontSize: 15, fontWeight: 600, color: '#374151',
          }}
        >
          <span style={{ fontSize: 12 }}>{expanded ? '▾' : '▸'}</span>
          Execution Timeline
          <span style={{ fontSize: 12, fontWeight: 400, color: '#9ca3af' }}>
            ({eventCount} event{eventCount !== 1 ? 's' : ''})
          </span>
        </button>
        <ConnectionStatusBadge status={connectionStatus} />
      </div>
      {expanded && (
        <div style={{ marginTop: 12 }}>
          <TimelineFeed events={events} memberMap={memberMap} />
        </div>
      )}
    </div>
  );
}
