'use client';

import type { Task } from '@keviq/domain-types';
import { useTaskTemplate } from '@keviq/server-state';

const dtStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: '#6b7280',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.05em',
  marginBottom: 2,
};

const ddStyle: React.CSSProperties = {
  fontSize: 14,
  color: '#111827',
  margin: 0,
  whiteSpace: 'pre-wrap' as const,
  lineHeight: 1.5,
};

const emptyStyle: React.CSSProperties = {
  ...ddStyle,
  color: '#9ca3af',
  fontStyle: 'italic' as const,
};

interface Props {
  task: Task;
}

export function TaskBriefSummary({ task }: Props) {
  const { data: template } = useTaskTemplate(task.template_id);

  const fields = [
    { label: 'Goal', value: task.goal },
    { label: 'Context', value: task.context },
    { label: 'Constraints', value: task.constraints },
    { label: 'Desired Output', value: task.desired_output },
  ];

  const hasAnyBrief = fields.some((f) => f.value);
  if (!hasAnyBrief && !template) return null;

  return (
    <div style={{ padding: 16, border: '1px solid #e5e7eb', borderRadius: 8, backgroundColor: '#fafafa' }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 12 }}>Task Brief</h3>

      {template && (
        <div style={{ marginBottom: 12 }}>
          <dt style={dtStyle}>Template</dt>
          <dd style={ddStyle}>{template.name} ({template.category})</dd>
        </div>
      )}

      {fields.map((f) => (
        <div key={f.label} style={{ marginBottom: 10 }}>
          <dt style={dtStyle}>{f.label}</dt>
          <dd style={f.value ? ddStyle : emptyStyle}>
            {f.value || 'Not specified'}
          </dd>
        </div>
      ))}
    </div>
  );
}
