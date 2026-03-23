'use client';

import type { TaskTemplate } from '@keviq/domain-types';
import { useTaskTemplates } from '@keviq/server-state';
import { loadingTextStyle, errorBoxStyle, errorBodyStyle } from '@/modules/shared/ui-styles';

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

const categoryBadge: React.CSSProperties = {
  display: 'inline-block',
  padding: '1px 6px',
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 500,
  backgroundColor: '#f3f4f6',
  color: '#6b7280',
};

interface Props {
  selectedId: string | null;
  onSelect: (template: TaskTemplate) => void;
}

export function TemplatePicker({ selectedId, onSelect }: Props) {
  const { data, isLoading, isError, error } = useTaskTemplates();

  if (isLoading) return <p style={loadingTextStyle}>Loading templates…</p>;
  if (isError) return <div style={errorBoxStyle}><p style={errorBodyStyle}>{String(error)}</p></div>;

  const templates = data?.items ?? [];
  if (templates.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
        Start from a template (optional)
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {templates.map((t) => (
          <div
            key={t.template_id}
            style={selectedId === t.template_id ? selectedCardStyle : cardStyle}
            onClick={() => onSelect(t)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelect(t)}
          >
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{t.name}</div>
            {t.description && (
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>{t.description}</div>
            )}
            <span style={categoryBadge}>{t.category}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
