'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { LineageEdge } from '@keviq/domain-types';
import { artifactDetailPath, runDetailPath } from '@keviq/routing';

interface LineageData {
  ancestors: LineageEdge[];
}

export function LineageCue({
  lineage,
  isLoading,
  isError,
  workspaceId,
  artifactId,
}: {
  lineage: LineageData | null | undefined;
  isLoading: boolean;
  isError: boolean;
  workspaceId: string;
  artifactId: string;
}) {
  const [expanded, setExpanded] = useState(false);

  if (isLoading) return <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading lineage...</p>;
  if (isError) return <p style={{ color: '#b91c1c', fontSize: 13 }}>Failed to load lineage.</p>;

  const ancestors = lineage?.ancestors ?? [];

  if (ancestors.length === 0) {
    return <p style={{ color: '#9ca3af', fontSize: 13 }}>Root artifact — no ancestors.</p>;
  }

  const count = ancestors.length;
  const firstParent = ancestors[0];
  const version = count + 1;
  const compareUrl = `${artifactDetailPath(workspaceId, artifactId)}?compare=${firstParent.parent_artifact_id}`;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
        <span style={{ fontSize: 14, color: '#374151' }}>
          {count} parent artifact{count > 1 ? 's' : ''} &rarr;{' '}
          <Link
            href={artifactDetailPath(workspaceId, firstParent.parent_artifact_id)}
            style={{ color: '#1d4ed8', textDecoration: 'none' }}
          >
            {firstParent.parent_artifact_id.slice(0, 8)}...
          </Link>
        </span>
        <span style={{
          fontSize: 11, padding: '2px 6px',
          backgroundColor: '#f3f4f6', color: '#374151',
          borderRadius: 4, fontWeight: 600,
        }}>
          This is v{version}
        </span>
        <Link
          href={compareUrl}
          style={{
            fontSize: 12, padding: '3px 10px',
            border: '1px solid #1d4ed8', borderRadius: 5,
            backgroundColor: '#eff6ff', color: '#1d4ed8',
            textDecoration: 'none', fontWeight: 500,
          }}
        >
          Compare to v{version - 1} →
        </Link>
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#6b7280', padding: 0 }}
      >
        {expanded ? '▾ Hide full lineage' : '▸ Show full lineage'}
      </button>

      {expanded && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '6px 8px', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>Parent artifact</th>
              <th style={{ padding: '6px 8px', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>Edge type</th>
              <th style={{ padding: '6px 8px', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>Run</th>
              <th style={{ padding: '6px 8px', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {ancestors.map((edge) => (
              <tr key={edge.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '6px 8px' }}>
                  <Link
                    href={artifactDetailPath(workspaceId, edge.parent_artifact_id)}
                    style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 13 }}
                  >
                    {edge.parent_artifact_id.slice(0, 8)}...
                  </Link>
                </td>
                <td style={{ padding: '6px 8px', fontSize: 13, color: '#6b7280' }}>
                  {edge.edge_type.replace(/_/g, ' ')}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  {edge.run_id ? (
                    <Link
                      href={runDetailPath(workspaceId, edge.run_id)}
                      style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 13 }}
                    >
                      {edge.run_id.slice(0, 8)}...
                    </Link>
                  ) : (
                    <span style={{ color: '#9ca3af', fontSize: 13 }}>&mdash;</span>
                  )}
                </td>
                <td style={{ padding: '6px 8px', fontSize: 13, color: '#6b7280' }}>
                  {new Date(edge.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
