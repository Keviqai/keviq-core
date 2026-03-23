import type { ConnectionStatus } from '@keviq/live-state';

const STATUS_CONFIG: Record<ConnectionStatus, { color: string; bg: string; label: string }> = {
  connecting: { color: '#92400e', bg: '#fef3c7', label: 'Connecting' },
  live: { color: '#065f46', bg: '#d1fae5', label: 'Live' },
  reconnecting: { color: '#92400e', bg: '#fef3c7', label: 'Reconnecting' },
  disconnected: { color: '#6b7280', bg: '#f3f4f6', label: 'Disconnected' },
};

export function ConnectionStatusBadge({ status }: { status: ConnectionStatus }) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 8px',
        borderRadius: 9999,
        fontSize: 11,
        fontWeight: 500,
        backgroundColor: config.bg,
        color: config.color,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: config.color,
        }}
      />
      {config.label}
    </span>
  );
}
