'use client';

import { useAgentTemplate } from '@keviq/server-state';

const riskColors: Record<string, { bg: string; text: string }> = {
  low: { bg: '#d1fae5', text: '#065f46' },
  medium: { bg: '#fef3c7', text: '#92400e' },
  high: { bg: '#fee2e2', text: '#991b1b' },
};

interface Props {
  agentTemplateId: string | undefined;
  riskLevel: string | null;
}

export function TaskAgentInfo({ agentTemplateId, riskLevel }: Props) {
  const { data: agent } = useAgentTemplate(agentTemplateId);

  if (!agentTemplateId) return null;
  if (!agent) return null;

  const rc = riskColors[riskLevel ?? agent.default_risk_profile] ?? riskColors.medium;

  return (
    <div style={{ padding: 16, border: '1px solid #e5e7eb', borderRadius: 8, backgroundColor: '#fafafa' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 4 }}>
            Agent: {agent.name}
          </h3>
          {agent.description && (
            <p style={{ fontSize: 13, color: '#6b7280', margin: 0, marginBottom: 8 }}>
              {agent.description}
            </p>
          )}
        </div>
        <span style={{
          display: 'inline-block',
          padding: '3px 10px',
          borderRadius: 9999,
          fontSize: 12,
          fontWeight: 600,
          backgroundColor: rc.bg,
          color: rc.text,
        }}>
          {(riskLevel ?? agent.default_risk_profile).toUpperCase()} RISK
        </span>
      </div>

      {agent.best_for && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#6b7280' }}>Best for: </span>
          <span style={{ fontSize: 12, color: '#374151' }}>{agent.best_for}</span>
        </div>
      )}
      {agent.not_for && (
        <div style={{ marginTop: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#6b7280' }}>Not for: </span>
          <span style={{ fontSize: 12, color: '#991b1b' }}>{agent.not_for}</span>
        </div>
      )}
    </div>
  );
}
