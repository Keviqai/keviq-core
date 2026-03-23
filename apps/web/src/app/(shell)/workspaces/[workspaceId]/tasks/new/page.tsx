'use client';

import { useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import type { TaskTemplate } from '@keviq/domain-types';
import { useCreateTaskDraft, useTaskTemplates } from '@keviq/server-state';
import { taskEditPath, tasksPath } from '@keviq/routing';
import {
  inputStyle,
  labelStyle,
  primaryButtonStyle,
  secondaryButtonStyle,
  errorBoxStyle,
  errorBodyStyle,
  loadingTextStyle,
} from '@/modules/shared/ui-styles';

const cardStyle: React.CSSProperties = {
  padding: 10,
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 13,
};

const selectedCard: React.CSSProperties = {
  ...cardStyle,
  borderColor: '#2563eb',
  backgroundColor: '#eff6ff',
};

export default function TaskNewPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const router = useRouter();
  const createDraft = useCreateTaskDraft();
  const { data: templateData } = useTaskTemplates();

  const [title, setTitle] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<TaskTemplate | null>(null);
  const [error, setError] = useState<string | null>(null);

  const templates = templateData?.items ?? [];

  const handleCreate = useCallback(() => {
    const trimmed = title.trim();
    if (!trimmed) {
      setError('Task title is required.');
      return;
    }
    setError(null);

    const payload: Record<string, unknown> = {
      workspace_id: workspaceId,
      title: trimmed,
    };
    if (selectedTemplate) {
      payload.template_id = selectedTemplate.template_id;
      const pf = selectedTemplate.prefilled_fields || {};
      if (pf.goal) payload.goal = pf.goal;
      if (pf.context) payload.context = pf.context;
      if (pf.constraints) payload.constraints = pf.constraints;
      if (pf.desired_output) payload.desired_output = pf.desired_output;
    }

    createDraft.mutate(payload as any, {
      onSuccess: (task) => {
        router.push(taskEditPath(workspaceId, task.task_id));
      },
      onError: (err) => {
        setError(err.message || 'Failed to create draft.');
      },
    });
  }, [title, selectedTemplate, workspaceId, createDraft, router]);

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={tasksPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Tasks
        </Link>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 20 }}>New Task</h1>

      <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Template selection */}
        {templates.length > 0 && (
          <div>
            <span style={{ ...labelStyle, marginBottom: 8, display: 'block' }}>
              Start from a template (optional)
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {templates.map((t) => (
                <div
                  key={t.template_id}
                  style={selectedTemplate?.template_id === t.template_id ? selectedCard : cardStyle}
                  onClick={() => setSelectedTemplate(
                    selectedTemplate?.template_id === t.template_id ? null : t,
                  )}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setSelectedTemplate(t)}
                >
                  <div style={{ fontWeight: 600, marginBottom: 2 }}>{t.name}</div>
                  {t.description && (
                    <div style={{ fontSize: 11, color: '#6b7280' }}>
                      {t.description.length > 60 ? t.description.slice(0, 60) + '…' : t.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Title */}
        <div>
          <label style={labelStyle}>Task Title *</label>
          <input
            style={inputStyle}
            value={title}
            onChange={(e) => { setTitle(e.target.value); setError(null); }}
            placeholder="e.g. Q1 Competitive Analysis"
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
        </div>

        {error && (
          <div style={errorBoxStyle}>
            <p style={errorBodyStyle}>{error}</p>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            style={{
              ...primaryButtonStyle,
              padding: '10px 20px',
              fontSize: 14,
              opacity: createDraft.isPending ? 0.6 : 1,
            }}
            onClick={handleCreate}
            disabled={createDraft.isPending || !title.trim()}
          >
            {createDraft.isPending ? 'Creating…' : 'Create Draft'}
          </button>
          <Link
            href={tasksPath(workspaceId)}
            style={{
              ...secondaryButtonStyle,
              padding: '10px 20px',
              fontSize: 14,
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            Cancel
          </Link>
        </div>
      </div>
    </div>
  );
}
