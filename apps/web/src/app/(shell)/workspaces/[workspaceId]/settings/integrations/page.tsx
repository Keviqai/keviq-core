'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useIntegrations, useCreateIntegration, useUpdateIntegration, useDeleteIntegration, useToggleIntegration, useSecrets } from '@keviq/server-state';
import type { Integration } from '@keviq/domain-types';
import { settingsPath } from '@keviq/routing';
import { useWorkspaceCapabilities } from '@/modules/shared/use-workspace-capabilities';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle } from '@/modules/shared/ui-styles';
import { IntegrationForm } from './_components/integration-form';

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  azure_openai: 'Azure OpenAI',
  custom: 'Custom',
};

export default function IntegrationsPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const { data: integrations, isLoading, isError, error } = useIntegrations(workspaceId);
  const { capabilities, isLoading: capsLoading } = useWorkspaceCapabilities(workspaceId);
  const canManage = capabilities.includes('workspace:manage_integrations');
  const { data: secrets } = useSecrets(canManage ? workspaceId : '');

  const createMut = useCreateIntegration();
  const toggleMut = useToggleIntegration();
  const deleteMut = useDeleteIntegration();
  const updateMut = useUpdateIntegration();

  const [showCreate, setShowCreate] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  if (isLoading || capsLoading) {
    return <p style={{ color: '#6b7280' }}>Loading integrations...</p>;
  }

  if (isError) {
    return (
      <div style={errorBoxStyle} role="alert">
        <p style={errorTitleStyle}>Failed to load integrations</p>
        <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
      </div>
    );
  }

  const list = integrations ?? [];

  function handleCreate(data: Parameters<typeof createMut.mutate>[0]['req']) {
    createMut.mutate(
      { workspaceId, req: data },
      { onSuccess: () => setShowCreate(false) },
    );
  }

  function handleDelete(integrationId: string) {
    deleteMut.mutate({ workspaceId, integrationId }, { onSuccess: () => setDeletingId(null) });
  }

  function handleEditSave(integration: Integration) {
    if (!editName.trim() || editName.trim() === integration.name) {
      setEditingId(null);
      return;
    }
    updateMut.mutate(
      { workspaceId, integrationId: integration.id, req: { name: editName.trim() } },
      { onSuccess: () => setEditingId(null) },
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={settingsPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Settings
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          Integrations
          {list.length > 0 && (
            <span style={{ fontWeight: 400, fontSize: 16, color: '#9ca3af', marginLeft: 8 }}>({list.length})</span>
          )}
        </h1>
        {canManage && !showCreate && list.length > 0 && (
          <button onClick={() => setShowCreate(true)} style={{
            padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
            backgroundColor: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 13,
          }}>
            Add Integration
          </button>
        )}
      </div>

      {showCreate && (
        <IntegrationForm
          secrets={secrets ?? []}
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
          isPending={createMut.isPending}
          error={createMut.isError ? (createMut.error?.message ?? 'Failed to create integration') : null}
        />
      )}

      {list.length === 0 && !showCreate ? (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 32, textAlign: 'center', maxWidth: 480 }}>
          <p style={{ fontSize: 16, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
            No integrations configured yet
          </p>
          <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 20, lineHeight: 1.5 }}>
            Add an LLM provider integration to connect your workspace to AI models.
          </p>
          {canManage && (
            <button onClick={() => setShowCreate(true)} style={{
              padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
              backgroundColor: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 14,
            }}>
              Add First Integration
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {list.map((item) => (
            <div key={item.id} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, backgroundColor: '#fafafa' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  {editingId === item.id ? (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                      <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
                        style={{ padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 14, fontWeight: 600 }}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleEditSave(item); if (e.key === 'Escape') setEditingId(null); }}
                        autoFocus
                      />
                      <button onClick={() => handleEditSave(item)} disabled={updateMut.isPending} style={{ fontSize: 12, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>Save</button>
                      <button onClick={() => setEditingId(null)} style={{ fontSize: 12, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }}>Cancel</button>
                    </div>
                  ) : (
                    <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0, marginBottom: 4 }}>{item.name}</h3>
                  )}
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, backgroundColor: '#eff6ff', color: '#1d4ed8', fontWeight: 500 }}>
                      {PROVIDER_LABELS[item.provider_kind] ?? item.provider_kind}
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 600,
                      backgroundColor: item.is_enabled ? '#dcfce7' : '#f3f4f6',
                      color: item.is_enabled ? '#166534' : '#6b7280',
                    }}>
                      {item.is_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                    {item.default_model && (
                      <span style={{ fontSize: 12, color: '#6b7280' }}>Model: {item.default_model}</span>
                    )}
                    {item.api_key_secret_ref && (
                      <span style={{ fontSize: 12, color: '#6b7280' }}>Secret: {item.api_key_secret_ref}</span>
                    )}
                  </div>
                  {item.endpoint_url && (
                    <p style={{ fontSize: 12, color: '#9ca3af', margin: '4px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 }}>
                      {item.endpoint_url}
                    </p>
                  )}
                  {item.description && (
                    <p style={{ fontSize: 12, color: '#9ca3af', margin: '4px 0 0' }}>{item.description}</p>
                  )}
                </div>

                {canManage && (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 16 }}>
                    {editingId !== item.id && (
                      <button onClick={() => { setEditingId(item.id); setEditName(item.name); }} style={{ fontSize: 12, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>
                        Edit
                      </button>
                    )}
                    <button onClick={() => toggleMut.mutate({ workspaceId, integrationId: item.id })}
                      disabled={toggleMut.isPending}
                      style={{ fontSize: 12, color: item.is_enabled ? '#d97706' : '#059669', background: 'none', border: 'none', cursor: 'pointer' }}>
                      {item.is_enabled ? 'Disable' : 'Enable'}
                    </button>
                    {deletingId === item.id ? (
                      <>
                        <button onClick={() => handleDelete(item.id)} disabled={deleteMut.isPending} style={{ fontSize: 12, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                          Confirm
                        </button>
                        <button onClick={() => setDeletingId(null)} style={{ fontSize: 12, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button onClick={() => setDeletingId(item.id)} style={{ fontSize: 12, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer' }}>
                        Delete
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {updateMut.isError && <p style={errorBodyStyle} role="alert">Update failed: {updateMut.error?.message ?? 'An unexpected error occurred.'}</p>}
      {deleteMut.isError && <p style={errorBodyStyle} role="alert">Delete failed: {deleteMut.error?.message ?? 'An unexpected error occurred.'}</p>}
    </div>
  );
}
