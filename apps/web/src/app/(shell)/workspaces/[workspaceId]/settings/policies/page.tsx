'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { usePolicies, useCreatePolicy, useUpdatePolicy } from '@keviq/server-state';
import { useWorkspaceCapabilities } from '@/modules/shared/use-workspace-capabilities';
import { settingsPath } from '@keviq/routing';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle, inputStyle, labelStyle, primaryButtonStyle, secondaryButtonStyle } from '@/modules/shared/ui-styles';

export default function PoliciesPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const { data: policies, isLoading, isError, error } = usePolicies(workspaceId);
  const { capabilities, isLoading: capsLoading } = useWorkspaceCapabilities(workspaceId);
  const canManage = capabilities.includes('workspace:manage_policy');

  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  if (isLoading || capsLoading) {
    return <p style={{ color: '#6b7280' }}>Loading policies...</p>;
  }

  if (isError) {
    return (
      <div style={errorBoxStyle} role="alert">
        <p style={errorTitleStyle}>Failed to load policies</p>
        <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
      </div>
    );
  }

  const policyList = policies ?? [];

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={settingsPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Settings
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          Policies
          {policyList.length > 0 && (
            <span style={{ fontWeight: 400, fontSize: 16, color: '#9ca3af', marginLeft: 8 }}>
              ({policyList.length})
            </span>
          )}
        </h1>
        {canManage && !showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            style={primaryButtonStyle}
          >
            Create Policy
          </button>
        )}
      </div>

      {showCreate && (
        <PolicyForm
          workspaceId={workspaceId}
          onDone={() => setShowCreate(false)}
        />
      )}

      {policyList.length === 0 && !showCreate ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#374151', marginBottom: 4 }}>No custom policies</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>Default role-based permissions are active.</p>
        </div>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Scope</th>
                <th style={thStyle}>Rules</th>
                <th style={thStyle}>Default</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {policyList.map((p) => (
                editingId === p.id ? (
                  <tr key={p.id}>
                    <td colSpan={5} style={{ padding: 12 }}>
                      <PolicyForm
                        workspaceId={workspaceId}
                        existing={p}
                        onDone={() => setEditingId(null)}
                      />
                    </td>
                  </tr>
                ) : (
                  <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={tdStyle}>{p.name}</td>
                    <td style={tdStyle}>{p.scope}</td>
                    <td style={tdStyle}>{Array.isArray(p.rules) ? p.rules.length : 0}</td>
                    <td style={tdStyle}>{p.is_default ? 'Yes' : 'No'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      {canManage && !p.is_default && (
                        <button
                          onClick={() => setEditingId(p.id)}
                          style={{ fontSize: 13, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const thStyle = { padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'left' as const, fontWeight: 500 };
const tdStyle = { padding: '10px 12px', fontSize: 14 };

/* ── Inline form for create / edit ───────────────────────────── */

interface PolicyFormProps {
  workspaceId: string;
  existing?: { id: string; name: string; scope: string; rules: unknown[] };
  onDone: () => void;
}

function PolicyForm({ workspaceId, existing, onDone }: PolicyFormProps) {
  const [name, setName] = useState(existing?.name ?? '');
  const [rulesJson, setRulesJson] = useState(
    existing?.rules ? JSON.stringify(existing.rules, null, 2) : '[]',
  );
  const [error, setError] = useState('');
  const createMut = useCreatePolicy();
  const updateMut = useUpdatePolicy();
  const submitting = createMut.isPending || updateMut.isPending;

  const handleSubmit = async () => {
    setError('');
    if (!name.trim()) { setError('Name is required'); return; }

    let rules: unknown[];
    try {
      rules = JSON.parse(rulesJson);
      if (!Array.isArray(rules)) throw new Error('not array');
    } catch {
      setError('Rules must be a valid JSON array');
      return;
    }

    try {
      if (existing) {
        await updateMut.mutateAsync({ workspaceId, policyId: existing.id, req: { name, rules } });
      } else {
        await createMut.mutateAsync({ workspaceId, req: { name, rules } });
      }
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save policy');
    }
  };

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 16, backgroundColor: '#fafafa' }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
        {existing ? 'Edit Policy' : 'Create Policy'}
      </h3>
      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={inputStyle}
        />
      </div>
      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>
          Rules (JSON array)
        </label>
        <textarea
          value={rulesJson}
          onChange={(e) => setRulesJson(e.target.value)}
          rows={4}
          style={{ ...inputStyle, fontSize: 13, fontFamily: 'monospace', resize: 'vertical' }}
        />
      </div>
      {error && <p style={{ color: '#991b1b', fontSize: 13, marginBottom: 8 }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          style={{ ...primaryButtonStyle, opacity: submitting ? 0.6 : 1 }}
        >
          {submitting ? 'Saving...' : existing ? 'Update' : 'Create'}
        </button>
        <button
          onClick={onDone}
          style={secondaryButtonStyle}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
