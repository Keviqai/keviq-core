'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useTask } from '@keviq/server-state';
import { tasksPath, taskDetailPath } from '@keviq/routing';
import { loadingTextStyle, errorBoxStyle, errorTitleStyle, errorBodyStyle, emptyStateBoxStyle } from '@/modules/shared/ui-styles';
import { TaskBriefForm } from '../../_components/task-brief-form';

export default function TaskEditPage() {
  const params = useParams<{ workspaceId: string; taskId: string }>();
  const { workspaceId, taskId } = params;
  const { data: task, isLoading, isError, error } = useTask(taskId);

  if (isLoading) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <p style={loadingTextStyle}>Loading task…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <Link href={tasksPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
            &larr; Tasks
          </Link>
        </div>
        <div style={errorBoxStyle}>
          <p style={errorTitleStyle}>Error loading task</p>
          <p style={errorBodyStyle}>{String(error)}</p>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div style={emptyStateBoxStyle}>
        <p>Task not found.</p>
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
          <p style={errorTitleStyle}>Cannot edit</p>
          <p style={errorBodyStyle}>
            Only draft tasks can be edited. This task is &quot;{task.task_status}&quot;.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={tasksPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Tasks
        </Link>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Edit Task Brief</h1>

      <div style={{ maxWidth: 700 }}>
        <TaskBriefForm task={task} workspaceId={workspaceId} />
      </div>
    </div>
  );
}
