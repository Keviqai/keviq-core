'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useSecrets, useCreateSecret, useDeleteSecret } from '@keviq/server-state';
import { useWorkspaceCapabilities } from '@/modules/shared/use-workspace-capabilities';
import { settingsPath } from '@keviq/routing';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle, inputStyle, labelStyle, primaryButtonStyle, secondaryButtonStyle } from '@/modules/shared/ui-styles';

const SECRET_TYPES = ['api_key', 'token', 'password', 'custom'] as const;

export default function SecretsPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const { data: secrets, isLoading, isError, error } = useSecrets(workspaceId);
  const { capabilities, isLoading: capsLoading } = useWorkspaceCapabilities(workspaceId);
  const canManage = capabilities.includes('workspace:manage_secrets');
  const deleteMut = useDeleteSecret();

  const [showCreate, setShowCreate] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  if (isLoading || capsLoading) {
    return <p style={{ color: '#6b7280' }}>Loading secrets...</p>;
  }

  if (isError) {
    return (
      <div style={errorBoxStyle} role="alert">
        <p style={errorTitleStyle}>Failed to load secrets</p>
        <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
      </div>
    );
  }

  if (!canManage) {
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <Link href={settingsPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
            &larr; Settings
          </Link>
        </div>
        <div style={errorBoxStyle} role="alert">
          <p style={errorTitleStyle}>Access denied</p>
          <p style={errorBodyStyle}>
            You do not have permission to manage secrets in this workspace.
          </p>
        </div>
      </div>
    );
  }

  const secretList = secrets ?? [];

  const handleDelete = async (secretId: string) => {
    try {
      await deleteMut.mutateAsync({ workspaceId, secretId });
      setDeletingId(null);
    } catch {
      // Error shown via deleteMut.isError
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={settingsPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Settings
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          Secrets
          {secretList.length > 0 && (
            <span style={{ fontWeight: 400, fontSize: 16, color: '#9ca3af', marginLeft: 8 }}>
              ({secretList.length})
            </span>
          )}
        </h1>
        {!showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            style={primaryButtonStyle}
          >
            Add Secret
          </button>
        )}
      </div>

      <p style={{ fontSize: 12, color: '#9ca3af', marginBottom: 16 }}>
        Secret values are encrypted and available to authorized services only.
      </p>

      {showCreate && (
        <SecretCreateForm workspaceId={workspaceId} onDone={() => setShowCreate(false)} />
      )}

      {secretList.length === 0 && !showCreate ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#374151', marginBottom: 4 }}>No secrets configured</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>Add API keys and credentials for your integrations.</p>
        </div>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Value</th>
                <th style={thStyle}>Created</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {secretList.map((s) => (
                <tr key={s.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={tdStyle}>{s.name}</td>
                  <td style={tdStyle}>
                    <span style={{ fontSize: 12, padding: '2px 8px', backgroundColor: '#f3f4f6', borderRadius: 4 }}>
                      {s.secret_type}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 13, color: '#6b7280' }}>
                    {s.masked_display}
                  </td>
                  <td style={{ ...tdStyle, fontSize: 13, color: '#6b7280' }}>
                    {new Date(s.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {deletingId === s.id ? (
                      <span style={{ fontSize: 13 }}>
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={deleteMut.isPending}
                          style={{ fontSize: 13, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', marginRight: 8 }}
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setDeletingId(null)}
                          style={{ fontSize: 13, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }}
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setDeletingId(s.id)}
                        style={{ fontSize: 13, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer' }}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deleteMut.isError && (
        <p style={{ color: '#991b1b', fontSize: 13, marginTop: 8 }}>
          Error: {deleteMut.error?.message ?? 'Failed to delete secret'}
        </p>
      )}
    </div>
  );
}

const thStyle = { padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'left' as const, fontWeight: 500 };
const tdStyle = { padding: '10px 12px', fontSize: 14 };

/* ── Create form ─────────────────────────────────────────────── */

function SecretCreateForm({ workspaceId, onDone }: { workspaceId: string; onDone: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [secretType, setSecretType] = useState<string>('api_key');
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const createMut = useCreateSecret();

  const handleSubmit = async () => {
    setError('');
    if (!name.trim()) { setError('Name is required'); return; }
    if (!value.trim()) { setError('Secret value is required'); return; }

    try {
      await createMut.mutateAsync({
        workspaceId,
        req: { name, description: description || undefined, secret_type: secretType, value },
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create secret');
    }
  };

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 16, backgroundColor: '#fafafa' }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Add Secret</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <label style={labelStyle}>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} placeholder="e.g. OPENAI_API_KEY" />
        </div>
        <div>
          <label style={labelStyle}>Type</label>
          <select value={secretType} onChange={(e) => setSecretType(e.target.value)} style={inputStyle}>
            {SECRET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>
      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Description (optional)</label>
        <input value={description} onChange={(e) => setDescription(e.target.value)} style={inputStyle} />
      </div>
      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Secret Value</label>
        <input type="password" value={value} onChange={(e) => setValue(e.target.value)} style={inputStyle} />
      </div>
      {error && <p style={{ color: '#991b1b', fontSize: 13, marginBottom: 8 }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={handleSubmit} disabled={createMut.isPending} style={{ ...primaryButtonStyle, opacity: createMut.isPending ? 0.6 : 1 }}>
          {createMut.isPending ? 'Creating...' : 'Create'}
        </button>
        <button onClick={onDone} style={secondaryButtonStyle}>Cancel</button>
      </div>
    </div>
  );
}

