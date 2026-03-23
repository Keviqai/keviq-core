'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useTask, useLaunchTask } from '@keviq/server-state';
import { taskEditPath, taskDetailPath, tasksPath } from '@keviq/routing';
import {
  loadingTextStyle,
  errorBoxStyle,
  errorTitleStyle,
  errorBodyStyle,
  primaryButtonStyle,
  secondaryButtonStyle,
} from '@/modules/shared/ui-styles';
import { ReviewPanel } from '../../_components/review-panel';
import { RiskScopeSummary } from '../../_components/risk-scope-summary';

export default function TaskReviewPage() {
  const params = useParams<{ workspaceId: string; taskId: string }>();
  const { workspaceId, taskId } = params;
  const router = useRouter();
  const { data: task, isLoading, isError, error } = useTask(taskId);
  const launchMut = useLaunchTask(workspaceId);
  const [launchError, setLaunchError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <p style={loadingTextStyle}>Loading task…</p>
      </div>
    );
  }

  if (isError || !task) {
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <Link href={tasksPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
            &larr; Tasks
          </Link>
        </div>
        <div style={errorBoxStyle}>
          <p style={errorTitleStyle}>Error loading task</p>
          <p style={errorBodyStyle}>{isError ? String(error) : 'Task not found'}</p>
        </div>
      </div>
    );
  }

  if (task.task_status !== 'draft') {
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <Link href={taskDetailPath(workspaceId, taskId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
            &larr; Back to task
          </Link>
        </div>
        <div style={errorBoxStyle}>
          <p style={errorTitleStyle}>Cannot review</p>
          <p style={errorBodyStyle}>
            Only draft tasks can be reviewed before launch. This task is &quot;{task.task_status}&quot;.
          </p>
        </div>
      </div>
    );
  }

  function handleLaunch() {
    setLaunchError(null);
    launchMut.mutate(taskId, {
      onSuccess: () => {
        router.push(taskDetailPath(workspaceId, taskId));
      },
      onError: (err) => {
        setLaunchError(err.message || 'Launch failed');
      },
    });
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={taskEditPath(workspaceId, taskId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Back to Edit Brief
        </Link>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Review Before Launch</h1>

      <div style={{ maxWidth: 700, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <ReviewPanel task={task} />
        <RiskScopeSummary agentTemplateId={task.agent_template_id} />

        {launchError && (
          <div style={errorBoxStyle}>
            <p style={errorTitleStyle}>Launch failed</p>
            <p style={errorBodyStyle}>{launchError}</p>
          </div>
        )}

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            style={{
              ...primaryButtonStyle,
              padding: '10px 24px',
              fontSize: 14,
              opacity: launchMut.isPending ? 0.6 : 1,
            }}
            onClick={handleLaunch}
            disabled={launchMut.isPending}
          >
            {launchMut.isPending ? 'Launching…' : 'Launch Task'}
          </button>
          <Link
            href={taskEditPath(workspaceId, taskId)}
            style={{
              ...secondaryButtonStyle,
              padding: '10px 24px',
              fontSize: 14,
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            Back to Edit
          </Link>
        </div>
      </div>
    </div>
  );
}
