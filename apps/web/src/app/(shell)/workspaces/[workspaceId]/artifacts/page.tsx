'use client';

import { useRef, useState, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useArtifactList, useArtifactUpload, useTaskList } from '@keviq/server-state';
import type { Artifact } from '@keviq/domain-types';
import { artifactDetailPath, runDetailPath, taskDetailPath, tasksPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { formatSize, formatArtifactType } from '@/modules/shared/format-utils';

function exportArtifactsCsv(items: Artifact[], workspaceId: string): void {
  const esc = (v: string | number | null | undefined) => {
    let s = String(v ?? '');
    // Prefix formula injection chars to prevent spreadsheet code execution
    if (/^[=+\-@]/.test(s)) s = ' ' + s;
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const headers = ['Name', 'Type', 'Status', 'Size (bytes)', 'Task ID', 'Run ID', 'Created'];
  const rows = items.map((a) =>
    [esc(a.name), esc(a.artifact_type), esc(a.artifact_status),
     esc(a.size_bytes), esc(a.task_id), esc(a.run_id), esc(a.created_at)].join(',')
  );
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `artifacts-${workspaceId.slice(0, 8)}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ArtifactListPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const { data, isLoading, isError, error } = useArtifactList(workspaceId);
  const { data: taskData } = useTaskList(workspaceId);
  const upload = useArtifactUpload(workspaceId);

  const taskTitleMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of taskData?.items ?? []) map.set(t.task_id, t.title);
    return map;
  }, [taskData]);

  const allTypes = useMemo(() => {
    if (!data) return [];
    const types = new Set(data.items.map((a) => a.artifact_type));
    return Array.from(types).sort();
  }, [data]);

  const filteredItems = useMemo(() => {
    if (!data) return [];
    if (!typeFilter) return data.items;
    return data.items.filter((a) => a.artifact_type === typeFilter);
  }, [data, typeFilter]);

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(
      { file },
      {
        onSuccess: (result) => {
          router.push(artifactDetailPath(workspaceId, result.id));
        },
      },
    );
    e.target.value = '';
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Outputs</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {filteredItems.length > 0 && (
            <button
              type="button"
              onClick={() => exportArtifactsCsv(filteredItems, workspaceId)}
              style={{
                padding: '8px 14px', fontSize: 13, fontWeight: 500,
                border: '1px solid #d1d5db', borderRadius: 6,
                backgroundColor: '#f9fafb', color: '#374151', cursor: 'pointer',
              }}
            >
              Export CSV
            </button>
          )}
          <input ref={fileInputRef} type="file" style={{ display: 'none' }} onChange={handleFileSelected} />
          <button
            type="button"
            disabled={upload.isPending}
            onClick={() => fileInputRef.current?.click()}
            style={{
              padding: '8px 16px', backgroundColor: '#1d4ed8', color: '#fff',
              border: 'none', borderRadius: 6,
              cursor: upload.isPending ? 'not-allowed' : 'pointer',
              opacity: upload.isPending ? 0.6 : 1,
              fontWeight: 600, fontSize: 14,
            }}
          >
            {upload.isPending ? 'Uploading...' : 'Upload artifact'}
          </button>
        </div>
      </div>

      {upload.isError && (
        <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca', marginBottom: 16 }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Upload failed</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            {upload.error instanceof Error ? upload.error.message : 'An unexpected error occurred.'}
          </p>
        </div>
      )}

      {isLoading && <p style={{ color: '#6b7280' }}>Loading artifacts...</p>}

      {isError && (
        <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load artifacts</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            {error instanceof Error ? error.message : 'An unexpected error occurred.'}
          </p>
        </div>
      )}

      {/* Type filter pills */}
      {allTypes.length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => setTypeFilter(null)}
            style={{
              fontSize: 12, padding: '4px 12px', borderRadius: 20,
              border: '1px solid #d1d5db', cursor: 'pointer',
              backgroundColor: typeFilter === null ? '#1d4ed8' : '#f9fafb',
              color: typeFilter === null ? '#fff' : '#374151',
            }}
          >
            All
          </button>
          {allTypes.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setTypeFilter(type === typeFilter ? null : type)}
              style={{
                fontSize: 12, padding: '4px 12px', borderRadius: 20,
                border: '1px solid #d1d5db', cursor: 'pointer',
                backgroundColor: typeFilter === type ? '#1d4ed8' : '#f9fafb',
                color: typeFilter === type ? '#fff' : '#374151',
              }}
            >
              {formatArtifactType(type)}
            </button>
          ))}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 16, marginBottom: 4 }}>No outputs yet</p>
          <p style={{ fontSize: 13, marginBottom: 8 }}>Outputs will appear here once tasks complete.</p>
          <p style={{ fontSize: 13 }}>
            <Link href={tasksPath(workspaceId)} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
              Create a task
            </Link>
            {' '}to generate artifacts, or upload a file above.
          </p>
        </div>
      )}

      {data && filteredItems.length === 0 && data.items.length > 0 && (
        <p style={{ color: '#9ca3af', fontSize: 13 }}>No artifacts match the selected filter.</p>
      )}

      {filteredItems.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '8px 12px' }}>Name</th>
              <th style={{ padding: '8px 12px' }}>Status</th>
              <th style={{ padding: '8px 12px' }}>Type</th>
              <th style={{ padding: '8px 12px' }}>Task</th>
              <th style={{ padding: '8px 12px' }}>Run</th>
              <th style={{ padding: '8px 12px' }}>Size</th>
              <th style={{ padding: '8px 12px' }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((artifact) => (
              <tr key={artifact.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '8px 12px' }}>
                  <Link href={artifactDetailPath(workspaceId, artifact.id)} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
                    {artifact.name}
                  </Link>
                </td>
                <td style={{ padding: '8px 12px' }}>
                  <StatusBadge status={artifact.artifact_status} />
                </td>
                <td style={{ padding: '8px 12px', color: '#6b7280' }}>{formatArtifactType(artifact.artifact_type)}</td>
                <td style={{ padding: '8px 12px' }}>
                  <Link
                    href={taskDetailPath(workspaceId, artifact.task_id)}
                    style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 13 }}
                  >
                    {(taskTitleMap.get(artifact.task_id) ?? artifact.task_id).length > 35
                      ? (taskTitleMap.get(artifact.task_id) ?? artifact.task_id).slice(0, 35) + '…'
                      : taskTitleMap.get(artifact.task_id) ?? `${artifact.task_id.slice(0, 8)}...`}
                  </Link>
                </td>
                <td style={{ padding: '8px 12px' }}>
                  {artifact.root_type === 'upload' ? (
                    <span style={{ color: '#6b7280', fontSize: 13 }}>Uploaded</span>
                  ) : (
                    <Link
                      href={runDetailPath(workspaceId, artifact.run_id)}
                      style={{ color: '#7c3aed', textDecoration: 'none', fontSize: 13 }}
                    >
                      View run
                    </Link>
                  )}
                </td>
                <td style={{ padding: '8px 12px', color: '#6b7280' }}>{formatSize(artifact.size_bytes)}</td>
                <td style={{ padding: '8px 12px', color: '#6b7280', fontSize: 13 }}>
                  {new Date(artifact.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
