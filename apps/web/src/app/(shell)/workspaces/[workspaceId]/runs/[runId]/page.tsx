'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo } from 'react';
import { useRun, useTask, useStepsByRun, useRunTimeline, useArtifactsByRun, useMembers } from '@keviq/server-state';
import { useEventStream } from '@keviq/live-state';
import { hasCapability } from '@keviq/permissions';
import { taskDetailPath, artifactDetailPath, tasksPath, terminalPath } from '@keviq/routing';
import { useState } from 'react';
import { StatusBadge } from '@/modules/shared/status-badge';
import { InvocationDebugPanel } from '@/modules/debug/invocation-debug-panel';
import { ToolExecutionViewer } from '@/modules/debug/tool-execution-viewer';
import { TimelineFeed, EMPTY_TIMELINE_EVENTS } from '@/modules/shared/timeline-feed';
import { buildMemberMap } from '@/modules/shared/member-map';
import { ConnectionStatusBadge } from '@/modules/shared/connection-status';
import { useEventInvalidation } from '@/modules/shared/use-event-invalidation';
import { formatDuration, formatSize, formatRelativeTime, formatArtifactType } from '@/modules/shared/format-utils';

export default function RunDetailPage() {
  const params = useParams<{ workspaceId: string; runId: string }>();
  const { workspaceId, runId } = params;
  const { data: run, isLoading, isError, error } = useRun(runId);
  const { data: stepsData } = useStepsByRun(runId);
  const { data: artifactsData } = useArtifactsByRun(workspaceId, runId);
  const { data: timelineData } = useRunTimeline(runId, workspaceId);
  const { data: members } = useMembers(workspaceId);
  const memberMap = useMemo(() => buildMemberMap(members), [members]);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const onInvalidate = useEventInvalidation();
  const { status: connectionStatus } = useEventStream({
    workspaceId,
    scope: { type: 'run', id: runId },
    onInvalidate,
  });
  // Fetch task title for human-friendly heading (must be before early returns)
  const { data: taskData } = useTask(run?.task_id ?? '');
  const taskTitle = taskData?.title;

  if (isLoading) {
    return <p style={{ color: '#6b7280' }}>Loading run...</p>;
  }

  if (isError || !run) {
    return (
      <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
        <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load run</p>
        <p style={{ color: '#b91c1c', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'Run not found or an unexpected error occurred.'}
        </p>
        <Link href={tasksPath(workspaceId)} style={{ color: '#1d4ed8', fontSize: 13 }}>
          Back to tasks
        </Link>
      </div>
    );
  }
  const canViewTask = hasCapability(run._capabilities, 'can_view_task');
  const steps = stepsData?.items ?? [];
  const artifacts = artifactsData?.items ?? [];
  const failedStep = steps.find((s) => s.step_status === 'failed');
  const completedSteps = steps.filter((s) => s.step_status === 'completed').length;
  const totalSteps = steps.length;
  const isRunning = run.run_status === 'running';
  const isFailed = run.run_status === 'failed' || run.run_status === 'timed_out';
  const isCompleted = run.run_status === 'completed';

  return (
    <div>
      {/* Back link */}
      <div style={{ marginBottom: 8 }}>
        <Link
          href={taskDetailPath(workspaceId, run.task_id)}
          style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}
        >
          &larr; Back to Task
        </Link>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, marginBottom: 6 }}>
            {taskTitle ? `Run — ${taskTitle}` : `Run ${run.run_id.slice(0, 8)}...`}
          </h1>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <StatusBadge status={run.run_status} />
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              Attempt #{run.attempt_number ?? 1}
            </span>
            <span style={{ fontSize: 13, color: '#9ca3af' }}>
              {formatDuration(run.started_at, run.completed_at)}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {run.sandbox_id && (
            <Link
              href={terminalPath(workspaceId, runId)}
              style={{
                padding: '4px 12px',
                backgroundColor: '#1e293b',
                color: '#e2e8f0',
                borderRadius: 6,
                fontSize: 13,
                textDecoration: 'none',
                fontFamily: 'monospace',
              }}
            >
              Terminal
            </Link>
          )}
          <ConnectionStatusBadge status={connectionStatus} />
        </div>
      </div>

      {/* ── Result Summary Block ── */}
      {isCompleted && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          backgroundColor: '#f0fdf4',
          border: '1px solid #a7f3d0',
          borderRadius: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 18 }}>&#10003;</span>
            <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#065f46' }}>
              Run Completed
            </h3>
          </div>
          <div style={{ fontSize: 13, color: '#047857' }}>
            {completedSteps > 0 && <span>{completedSteps} step{completedSteps !== 1 ? 's' : ''} completed</span>}
            {artifacts.length > 0 && (
              <span style={{ marginLeft: completedSteps > 0 ? 12 : 0 }}>
                {artifacts.length} artifact{artifacts.length !== 1 ? 's' : ''} produced
              </span>
            )}
            {run.completed_at && (
              <span style={{ marginLeft: 12, color: '#6b7280' }}>
                Finished {formatRelativeTime(run.completed_at)}
              </span>
            )}
          </div>
        </div>
      )}

      {isFailed && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          backgroundColor: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 18, color: '#991b1b' }}>&#10007;</span>
            <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#991b1b' }}>
              {run.run_status === 'timed_out' ? 'Run Timed Out' : 'Run Failed'}
            </h3>
          </div>
          {run.error_summary && (
            <p style={{ margin: 0, marginBottom: 8, fontSize: 14, color: '#b91c1c', lineHeight: 1.5 }}>
              {run.error_summary}
            </p>
          )}
          {failedStep && (
            <p style={{ margin: 0, fontSize: 13, color: '#991b1b' }}>
              Failed at step #{failedStep.sequence_number} ({failedStep.step_type})
              {failedStep.error_detail != null && typeof failedStep.error_detail === 'object' && 'message' in (failedStep.error_detail as object) && (
                <> &mdash; {String((failedStep.error_detail as Record<string, unknown>).message)}</>
              )}
            </p>
          )}
          {run.completed_at && (
            <p style={{ margin: 0, marginTop: 8, fontSize: 12, color: '#9ca3af' }}>
              {run.run_status === 'timed_out' ? 'Timed out' : 'Failed'} {formatRelativeTime(run.completed_at)}
            </p>
          )}
        </div>
      )}

      {isRunning && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          backgroundColor: '#eff6ff',
          border: '2px solid #93c5fd',
          borderRadius: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: '#3b82f6',
              animation: 'pulse 2s infinite',
            }} />
            <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#1e40af' }}>
              Running
            </h3>
          </div>
          <div style={{ fontSize: 13, color: '#1e40af' }}>
            {totalSteps > 0 && (
              <span>{completedSteps}/{totalSteps} steps completed</span>
            )}
            {run.started_at && (
              <span style={{ marginLeft: totalSteps > 0 ? 12 : 0, color: '#6b7280' }}>
                Started {formatRelativeTime(run.started_at)}
              </span>
            )}
          </div>
        </div>
      )}

      {run.run_status === 'pending' && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          backgroundColor: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: 8,
        }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#92400e', marginBottom: 4 }}>
            Queued
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: '#b45309' }}>
            This run is waiting to start execution.
          </p>
        </div>
      )}

      {run.run_status === 'cancelled' && (
        <div style={{
          marginBottom: 24,
          padding: 16,
          backgroundColor: '#f9fafb',
          border: '1px solid #e5e7eb',
          borderRadius: 8,
        }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#6b7280', marginBottom: 4 }}>
            Cancelled
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: '#9ca3af' }}>
            This run was cancelled before completing.
          </p>
        </div>
      )}

      {/* ── Metadata Row ── */}
      <div style={{
        display: 'flex',
        gap: 24,
        marginBottom: 24,
        flexWrap: 'wrap',
        padding: 12,
        backgroundColor: '#f9fafb',
        borderRadius: 8,
        fontSize: 13,
      }}>
        <div>
          <span style={{ color: '#6b7280' }}>Started</span>
          <p style={{ margin: 0, marginTop: 2 }}>
            {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <span style={{ color: '#6b7280' }}>Completed</span>
          <p style={{ margin: 0, marginTop: 2 }}>
            {run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <span style={{ color: '#6b7280' }}>Duration</span>
          <p style={{ margin: 0, marginTop: 2 }}>
            {formatDuration(run.started_at, run.completed_at)}
          </p>
        </div>
        {canViewTask && (
          <div>
            <span style={{ color: '#6b7280' }}>Task</span>
            <p style={{ margin: 0, marginTop: 2 }}>
              <Link
                href={taskDetailPath(workspaceId, run.task_id)}
                style={{ color: '#1d4ed8', textDecoration: 'none' }}
              >
                {taskTitle ?? `${run.task_id.slice(0, 8)}...`}
              </Link>
            </p>
          </div>
        )}
      </div>

      {/* ── Steps ── */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#374151' }}>
          Steps {totalSteps > 0 && <span style={{ fontWeight: 400, color: '#9ca3af' }}>({completedSteps}/{totalSteps})</span>}
        </h3>
        {!stepsData && <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading steps...</p>}
        {stepsData && steps.length === 0 && (
          <p style={{ color: '#9ca3af', fontSize: 13 }}>
            {isRunning ? 'Steps will appear as execution progresses.' : 'No steps recorded for this run.'}
          </p>
        )}
        {steps.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {steps.map((step) => {
              const isStepFailed = step.step_status === 'failed';
              return (
                <div
                  key={step.step_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '8px 0',
                    borderBottom: '1px solid #f3f4f6',
                    backgroundColor: isStepFailed ? '#fef2f2' : 'transparent',
                    marginLeft: isStepFailed ? -8 : 0,
                    marginRight: isStepFailed ? -8 : 0,
                    paddingLeft: isStepFailed ? 8 : 0,
                    paddingRight: isStepFailed ? 8 : 0,
                    borderRadius: isStepFailed ? 4 : 0,
                  }}
                >
                  <span style={{ fontSize: 13, color: '#9ca3af', minWidth: 24, textAlign: 'right' }}>
                    #{step.sequence_number}
                  </span>
                  <span style={{ fontSize: 13, flex: 1 }}>
                    {step.step_type}
                  </span>
                  <StatusBadge status={step.step_status} />
                  <span style={{ fontSize: 12, color: '#9ca3af', minWidth: 50, textAlign: 'right' }}>
                    {formatDuration(step.started_at, step.completed_at)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Outputs ── */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#374151' }}>
          Outputs {artifacts.length > 0 && <span style={{ fontWeight: 400, color: '#9ca3af' }}>({artifacts.length})</span>}
        </h3>
        {!artifactsData && <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading outputs...</p>}
        {artifactsData && artifacts.length === 0 && (
          <p style={{ color: '#9ca3af', fontSize: 13 }}>
            {isRunning
              ? 'Outputs will appear as they are produced.'
              : isFailed
                ? 'No output was saved because the run failed before completing.'
                : 'The run completed, but the AI model did not produce a saved output. This can happen if the response was empty.'}
          </p>
        )}
        {artifacts.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {artifacts.map((artifact) => (
              <div
                key={artifact.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '8px 0',
                  borderBottom: '1px solid #f3f4f6',
                }}
              >
                <Link
                  href={artifactDetailPath(workspaceId, artifact.id)}
                  style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 13, flex: 1 }}
                >
                  {artifact.name}
                </Link>
                <span style={{ fontSize: 12, color: '#9ca3af' }}>
                  {formatArtifactType(artifact.artifact_type)}
                </span>
                <span style={{ fontSize: 12, color: '#9ca3af' }}>
                  {formatSize(artifact.size_bytes)}
                </span>
                <StatusBadge status={artifact.artifact_status} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Timeline ── */}
      {/* O6-S4: Invocation debug panel — collapsible, before timeline */}
      <InvocationDebugPanel events={timelineData?.events ?? EMPTY_TIMELINE_EVENTS} />

      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: '#374151' }}>Timeline</h3>
          <ConnectionStatusBadge status={connectionStatus} />
        </div>
        <TimelineFeed
          events={timelineData?.events ?? EMPTY_TIMELINE_EVENTS}
          onSelectExecution={setSelectedExecutionId}
          memberMap={memberMap}
        />
      </div>

      {/* O7-S2: Tool execution detail viewer — shows when execution_id is selected */}
      {selectedExecutionId && (
        <ToolExecutionViewer
          executionId={selectedExecutionId}
          onClose={() => setSelectedExecutionId(null)}
        />
      )}
    </div>
  );
}
