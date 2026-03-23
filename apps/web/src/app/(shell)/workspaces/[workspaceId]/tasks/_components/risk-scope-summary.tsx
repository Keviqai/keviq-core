'use client';

import { useAgentTemplate } from '@keviq/server-state';
import { loadingTextStyle } from '@/modules/shared/ui-styles';

const riskColors: Record<string, { bg: string; text: string }> = {
  low: { bg: '#d1fae5', text: '#065f46' },
  medium: { bg: '#fef3c7', text: '#92400e' },
  high: { bg: '#fee2e2', text: '#991b1b' },
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: '#6b7280',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.05em',
  marginBottom: 4,
};

const capBadge: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: 11,
  backgroundColor: '#f3f4f6',
  color: '#374151',
  marginRight: 4,
  marginBottom: 4,
};

interface Props {
  agentTemplateId: string | undefined;
}

export function RiskScopeSummary({ agentTemplateId }: Props) {
  const { data: agent, isLoading } = useAgentTemplate(agentTemplateId);

  if (!agentTemplateId) {
    return (
      <div style={{ padding: 16, border: '1px solid #fecaca', borderRadius: 8, backgroundColor: '#fef2f2' }}>
        <p style={{ color: '#991b1b', fontSize: 13, margin: 0 }}>
          No agent selected. Please go back and choose an agent before launching.
        </p>
      </div>
    );
  }

  if (isLoading) return <p style={loadingTextStyle}>Loading agent info…</p>;

  if (!agent) {
    return (
      <div style={{ padding: 16, border: '1px solid #fecaca', borderRadius: 8, backgroundColor: '#fef2f2' }}>
        <p style={{ color: '#991b1b', fontSize: 13, margin: 0 }}>Agent template not found.</p>
      </div>
    );
  }

  const rc = riskColors[agent.default_risk_profile] ?? riskColors.medium;

  return (
    <div style={{ padding: 20, border: '1px solid #e5e7eb', borderRadius: 8, backgroundColor: '#fafafa' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 0, marginBottom: 16 }}>
        Agent & Risk Summary
      </h2>

      <div style={{ marginBottom: 12 }}>
        <span style={labelStyle}>Agent</span>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#111827' }}>{agent.name}</div>
        {agent.description && (
          <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>{agent.description}</div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <span style={labelStyle}>Risk Level</span>
        <div>
          <span style={{
            display: 'inline-block',
            padding: '3px 10px',
            borderRadius: 9999,
            fontSize: 12,
            fontWeight: 600,
            backgroundColor: rc.bg,
            color: rc.text,
          }}>
            {agent.default_risk_profile.toUpperCase()}
          </span>
        </div>
      </div>

      {agent.capabilities_manifest.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={labelStyle}>Capabilities</span>
          <div style={{ marginTop: 4 }}>
            {agent.capabilities_manifest.map((cap) => (
              <span key={cap} style={capBadge}>{cap.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </div>
      )}

      {agent.best_for && (
        <div style={{ marginBottom: 12 }}>
          <span style={labelStyle}>Best For</span>
          <div style={{ fontSize: 13, color: '#374151' }}>{agent.best_for}</div>
        </div>
      )}

      {agent.not_for && (
        <div style={{ marginBottom: 0 }}>
          <span style={labelStyle}>Not Recommended For</span>
          <div style={{ fontSize: 13, color: '#991b1b' }}>{agent.not_for}</div>
        </div>
      )}
    </div>
  );
}
