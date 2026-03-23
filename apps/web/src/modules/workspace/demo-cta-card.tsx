'use client';

import Link from 'next/link';
import { taskNewPath } from '@keviq/routing';

export function DemoCTACard({ workspaceId }: { workspaceId: string }) {
  return (
    <div style={{
      padding: 20,
      backgroundColor: '#eff6ff',
      border: '1px solid #bfdbfe',
      borderRadius: 8,
      marginBottom: 24,
    }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: '#1e3a5f', marginBottom: 6 }}>
        Try a demo task
      </h3>
      <p style={{ fontSize: 14, color: '#374151', marginBottom: 14, lineHeight: 1.5 }}>
        See Keviq Core in action. Create a task that generates a workspace status report,
        then follow the run through to the finished artifact.
      </p>
      <Link
        href={taskNewPath(workspaceId) + '?template=demo'}
        style={{
          display: 'inline-block',
          padding: '8px 18px',
          backgroundColor: '#1d4ed8',
          color: '#fff',
          borderRadius: 6,
          fontSize: 14,
          fontWeight: 600,
          textDecoration: 'none',
        }}
      >
        Start demo task &rarr;
      </Link>
    </div>
  );
}
