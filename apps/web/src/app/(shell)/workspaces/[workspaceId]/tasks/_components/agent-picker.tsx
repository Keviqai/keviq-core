'use client';

import type { AgentTemplate } from '@keviq/domain-types';
import { useAgentTemplates } from '@keviq/server-state';
import { loadingTextStyle, errorBoxStyle, errorBodyStyle } from '@/modules/shared/ui-styles';

const riskColors: Record<string, { bg: string; text: string }> = {
  low: { bg: '#d1fae5', text: '#065f46' },
  medium: { bg: '#fef3c7', text: '#92400e' },
  high: { bg: '#fee2e2', text: '#991b1b' },
};

const cardStyle: React.CSSProperties = {
  padding: 12,
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  cursor: 'pointer',
  transition: 'border-color 0.15s',
};

const selectedCardStyle: React.CSSProperties = {
  ...cardStyle,
  borderColor: '#2563eb',
  backgroundColor: '#eff6ff',
};

interface Props {
  selectedId: string | null;
  onSelect: (agent: AgentTemplate) => void;
}

export function AgentPicker({ selectedId, onSelect }: Props) {
  const { data, isLoading, isError, error } = useAgentTemplates();

  if (isLoading) return <p style={loadingTextStyle}>Loading agents…</p>;
  if (isError) return <div style={errorBoxStyle}><p style={errorBodyStyle}>{String(error)}</p></div>;

  const agents = data?.items ?? [];
  if (agents.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
        Choose an agent
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {agents.map((a) => {
          const rc = riskColors[a.default_risk_profile] ?? riskColors.medium;
          return (
            <div
              key={a.template_id}
              style={selectedId === a.template_id ? selectedCardStyle : cardStyle}
              onClick={() => onSelect(a)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(a)}
            >
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{a.name}</div>
              {a.description && (
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
                  {a.description}
                </div>
              )}
              {a.best_for && (
                <div style={{ fontSize: 11, color: '#374151', marginBottom: 4 }}>
                  <strong>Best for:</strong> {a.best_for}
                </div>
              )}
              <span
                style={{
                  display: 'inline-block',
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: 500,
                  backgroundColor: rc.bg,
                  color: rc.text,
                }}
              >
                {a.default_risk_profile} risk
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
