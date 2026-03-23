'use client';

import { useState, useCallback } from 'react';
import type { Task, TaskTemplate, AgentTemplate } from '@keviq/domain-types';
import { useUpdateTaskBrief } from '@keviq/server-state';
import Link from 'next/link';
import { taskReviewPath } from '@keviq/routing';
import { inputStyle, labelStyle, primaryButtonStyle, secondaryButtonStyle, errorBoxStyle, errorBodyStyle } from '@/modules/shared/ui-styles';
import { TemplatePicker } from './template-picker';
import { AgentPicker } from './agent-picker';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const textareaStyle: React.CSSProperties = {
  ...inputStyle,
  minHeight: 80,
  resize: 'vertical' as const,
  fontFamily: 'inherit',
};

const helperStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#9ca3af',
  marginTop: 2,
};

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
};

interface Props {
  task: Task;
  workspaceId: string;
}

export function TaskBriefForm({ task, workspaceId }: Props) {
  const [title, setTitle] = useState(task.title || '');
  const [goal, setGoal] = useState(task.goal || '');
  const [context, setContext] = useState(task.context || '');
  const [constraints, setConstraints] = useState(task.constraints || '');
  const [desiredOutput, setDesiredOutput] = useState(task.desired_output || '');
  const [templateId, setTemplateId] = useState<string | null>(task.template_id ?? null);
  const [agentTemplateId, setAgentTemplateId] = useState<string | null>(task.agent_template_id ?? null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);

  const updateMut = useUpdateTaskBrief(workspaceId);

  const handleSave = useCallback(() => {
    setSaveStatus('saving');
    setSaveError(null);
    const updates: Record<string, unknown> = {
      title: title.trim(),
      goal: goal.trim() || null,
      context: context.trim() || null,
      constraints: constraints.trim() || null,
      desired_output: desiredOutput.trim() || null,
      template_id: templateId,
      agent_template_id: agentTemplateId,
    };
    updateMut.mutate(
      { taskId: task.task_id, updates },
      {
        onSuccess: () => setSaveStatus('saved'),
        onError: (err) => {
          setSaveStatus('error');
          setSaveError(err.message || 'Failed to save');
        },
      },
    );
  }, [title, goal, context, constraints, desiredOutput, templateId, agentTemplateId, task.task_id, updateMut]);

  const handleTemplateSelect = useCallback((t: TaskTemplate) => {
    setTemplateId(t.template_id);
    const pf = t.prefilled_fields || {};
    if (pf.goal) setGoal(pf.goal);
    if (pf.context) setContext(pf.context);
    if (pf.constraints) setConstraints(pf.constraints);
    if (pf.desired_output) setDesiredOutput(pf.desired_output);
  }, []);

  const handleAgentSelect = useCallback((a: AgentTemplate) => {
    setAgentTemplateId(a.template_id);
  }, []);

  const saveLabel =
    saveStatus === 'saving' ? 'Saving…' :
    saveStatus === 'saved' ? '✓ Saved' :
    saveStatus === 'error' ? 'Save Failed — Retry' :
    'Save Draft';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Template Picker */}
      <TemplatePicker selectedId={templateId} onSelect={handleTemplateSelect} />

      {/* Title */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Task Title *</label>
        <input
          style={inputStyle}
          value={title}
          onChange={(e) => { setTitle(e.target.value); setSaveStatus('idle'); }}
          placeholder="e.g. Q1 Competitive Analysis"
        />
      </div>

      {/* Goal */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Goal *</label>
        <textarea
          style={textareaStyle}
          value={goal}
          onChange={(e) => { setGoal(e.target.value); setSaveStatus('idle'); }}
          placeholder="What should the agent accomplish?"
        />
        <span style={helperStyle}>Describe the objective clearly. e.g. "Research top 5 competitors and summarize their pricing models."</span>
      </div>

      {/* Context */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Context</label>
        <textarea
          style={textareaStyle}
          value={context}
          onChange={(e) => { setContext(e.target.value); setSaveStatus('idle'); }}
          placeholder="Background information the agent should know"
        />
        <span style={helperStyle}>Provide relevant background. e.g. "We are a B2B SaaS company targeting mid-market."</span>
      </div>

      {/* Constraints */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Constraints</label>
        <textarea
          style={textareaStyle}
          value={constraints}
          onChange={(e) => { setConstraints(e.target.value); setSaveStatus('idle'); }}
          placeholder="Limitations or rules the agent must follow"
        />
        <span style={helperStyle}>e.g. "Use only public data sources. Do not include pricing estimates."</span>
      </div>

      {/* Desired Output */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Desired Output *</label>
        <textarea
          style={textareaStyle}
          value={desiredOutput}
          onChange={(e) => { setDesiredOutput(e.target.value); setSaveStatus('idle'); }}
          placeholder="What artifact or deliverable should be produced?"
        />
        <span style={helperStyle}>e.g. "A 3-page report with executive summary, competitor profiles, and recommendations."</span>
      </div>

      {/* Agent Picker */}
      <AgentPicker selectedId={agentTemplateId} onSelect={handleAgentSelect} />

      {/* Save + Error */}
      {saveError && (
        <div style={errorBoxStyle}>
          <p style={errorBodyStyle}>{saveError}</p>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button
          style={{
            ...primaryButtonStyle,
            opacity: saveStatus === 'saving' ? 0.6 : 1,
          }}
          onClick={handleSave}
          disabled={saveStatus === 'saving' || !title.trim()}
        >
          {saveLabel}
        </button>
        {saveStatus === 'saved' && (
          <>
            <span style={{ fontSize: 12, color: '#059669' }}>Draft saved successfully</span>
            <Link
              href={taskReviewPath(workspaceId, task.task_id)}
              style={{
                ...secondaryButtonStyle,
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              Review &amp; Launch →
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
