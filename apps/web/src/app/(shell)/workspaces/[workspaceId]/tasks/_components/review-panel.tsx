'use client';

import type { Task } from '@keviq/domain-types';
import { useTaskTemplate } from '@keviq/server-state';

const dtStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: '#6b7280',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.05em',
  marginBottom: 4,
};

const ddStyle: React.CSSProperties = {
  fontSize: 14,
  color: '#111827',
  margin: 0,
  whiteSpace: 'pre-wrap' as const,
};

const emptyStyle: React.CSSProperties = {
  ...ddStyle,
  color: '#9ca3af',
  fontStyle: 'italic' as const,
};

const sectionStyle: React.CSSProperties = {
  marginBottom: 16,
};

interface Props {
  task: Task;
}

export function ReviewPanel({ task }: Props) {
  const { data: template } = useTaskTemplate(task.template_id);

  return (
    <div style={{ padding: 20, border: '1px solid #e5e7eb', borderRadius: 8, backgroundColor: '#fafafa' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 0, marginBottom: 16 }}>
        Task Brief Summary
      </h2>

      <div style={sectionStyle}>
        <dt style={dtStyle}>Title</dt>
        <dd style={ddStyle}>{task.title}</dd>
      </div>

      {template && (
        <div style={sectionStyle}>
          <dt style={dtStyle}>Template</dt>
          <dd style={ddStyle}>{template.name} ({template.category})</dd>
        </div>
      )}

      <div style={sectionStyle}>
        <dt style={dtStyle}>Goal</dt>
        <dd style={task.goal ? ddStyle : emptyStyle}>
          {task.goal || 'Not specified'}
        </dd>
      </div>

      <div style={sectionStyle}>
        <dt style={dtStyle}>Context</dt>
        <dd style={task.context ? ddStyle : emptyStyle}>
          {task.context || 'Not specified'}
        </dd>
      </div>

      <div style={sectionStyle}>
        <dt style={dtStyle}>Constraints</dt>
        <dd style={task.constraints ? ddStyle : emptyStyle}>
          {task.constraints || 'Not specified'}
        </dd>
      </div>

      <div style={{ marginBottom: 0 }}>
        <dt style={dtStyle}>Desired Output</dt>
        <dd style={task.desired_output ? ddStyle : emptyStyle}>
          {task.desired_output || 'Not specified'}
        </dd>
      </div>
    </div>
  );
}
