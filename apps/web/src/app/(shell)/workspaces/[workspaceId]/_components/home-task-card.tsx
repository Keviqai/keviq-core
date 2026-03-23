import Link from 'next/link';
import type { Task } from '@keviq/domain-types';
import { taskDetailPath, taskEditPath, taskReviewPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { formatRelativeTime } from '@/modules/shared/format-utils';

function getAction(task: Task, workspaceId: string): { label: string; href: string } {
  if (task.task_status === 'draft') {
    const hasRequiredFields = task.goal && task.agent_template_id;
    if (hasRequiredFields) {
      return { label: 'Review', href: taskReviewPath(workspaceId, task.task_id) };
    }
    return { label: 'Edit Brief', href: taskEditPath(workspaceId, task.task_id) };
  }
  return { label: 'View Task', href: taskDetailPath(workspaceId, task.task_id) };
}

interface Props {
  task: Task;
  workspaceId: string;
}

export function HomeTaskCard({ task, workspaceId }: Props) {
  const action = getAction(task, workspaceId);
  const truncTitle = task.title.length > 50 ? task.title.slice(0, 50) + '…' : task.title;
  const cardHref = taskDetailPath(workspaceId, task.task_id);

  return (
    <Link href={cardHref} style={{ textDecoration: 'none', color: 'inherit' }}>
      <div style={{
        padding: 12, border: '1px solid #e5e7eb', borderRadius: 8,
        display: 'flex', flexDirection: 'column', gap: 8,
        cursor: 'pointer', transition: 'border-color 0.15s',
      }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = '#93c5fd'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = '#e5e7eb'; }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>{truncTitle}</span>
          <StatusBadge status={task.task_status} />
        </div>
        {task.goal && (
          <span style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.4 }}>
            {task.goal.length > 80 ? task.goal.slice(0, 80) + '…' : task.goal}
          </span>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
          <span style={{ fontSize: 11, color: '#9ca3af' }}>
            {formatRelativeTime(task.updated_at)}
          </span>
          <span style={{ fontSize: 12, color: '#2563eb', fontWeight: 500 }}>
            {action.label} →
          </span>
        </div>
      </div>
    </Link>
  );
}
