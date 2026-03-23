import Link from 'next/link';

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 12,
};

interface Props {
  title: string;
  viewAllHref?: string;
  emptyText?: string;
  children: React.ReactNode;
  isEmpty?: boolean;
}

export function HomeSection({ title, viewAllHref, emptyText, children, isEmpty }: Props) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
      <div style={headerStyle}>
        <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{title}</h3>
        {viewAllHref && !isEmpty && (
          <Link href={viewAllHref} style={{ fontSize: 13, color: '#1d4ed8', textDecoration: 'none' }}>
            View all &rarr;
          </Link>
        )}
      </div>
      {isEmpty ? (
        <p style={{ fontSize: 13, color: '#9ca3af', margin: 0 }}>
          {emptyText || 'Nothing here yet.'}
        </p>
      ) : (
        children
      )}
    </div>
  );
}
