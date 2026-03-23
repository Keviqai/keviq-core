const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: '#e0e7ff', text: '#3730a3' },
  pending: { bg: '#fef3c7', text: '#92400e' },
  running: { bg: '#dbeafe', text: '#1e40af' },
  waiting_approval: { bg: '#fef9c3', text: '#854d0e' },
  approved: { bg: '#d1fae5', text: '#065f46' },
  completed: { bg: '#d1fae5', text: '#065f46' },
  rejected: { bg: '#fee2e2', text: '#991b1b' },
  failed: { bg: '#fee2e2', text: '#991b1b' },
  timed_out: { bg: '#fee2e2', text: '#991b1b' },
  cancelled: { bg: '#f3f4f6', text: '#6b7280' },
  archived: { bg: '#f3f4f6', text: '#6b7280' },
};

export function StatusBadge({ status }: { status: string }) {
  const c = STATUS_COLORS[status] ?? { bg: '#f3f4f6', text: '#374151' };

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 9999,
        fontSize: 12,
        fontWeight: 500,
        backgroundColor: c.bg,
        color: c.text,
      }}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}
