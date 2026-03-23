'use client';

import { useState } from 'react';
import type { Secret } from '@keviq/domain-types';
import { inputStyle, labelStyle, primaryButtonStyle, secondaryButtonStyle } from '@/modules/shared/ui-styles';

const PROVIDER_KINDS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'azure_openai', label: 'Azure OpenAI' },
  { value: 'custom', label: 'Custom' },
];

interface IntegrationFormProps {
  secrets: Secret[];
  onSubmit: (data: {
    name: string;
    integration_type: string;
    provider_kind: string;
    endpoint_url?: string;
    default_model?: string;
    api_key_secret_ref?: string;
    description?: string;
  }) => void;
  onCancel: () => void;
  isPending: boolean;
  error?: string | null;
}

export function IntegrationForm({ secrets, onSubmit, onCancel, isPending, error }: IntegrationFormProps) {
  const [name, setName] = useState('');
  const [providerKind, setProviderKind] = useState('openai');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [defaultModel, setDefaultModel] = useState('');
  const [secretRef, setSecretRef] = useState('');
  const [description, setDescription] = useState('');

  const showEndpoint = providerKind === 'custom' || providerKind === 'azure_openai';

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name: name.trim(),
      integration_type: 'llm_provider',
      provider_kind: providerKind,
      endpoint_url: endpointUrl.trim() || undefined,
      default_model: defaultModel.trim() || undefined,
      api_key_secret_ref: secretRef || undefined,
      description: description.trim() || undefined,
    });
  }

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20, marginBottom: 16, backgroundColor: '#fafafa' }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 16 }}>Add LLM Provider</h3>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>Name</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} placeholder="My OpenAI" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Provider</label>
            <select value={providerKind} onChange={(e) => setProviderKind(e.target.value)} style={inputStyle}>
              {PROVIDER_KINDS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
        </div>

        {showEndpoint && (
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Endpoint URL</label>
            <input type="url" value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} placeholder="https://api.example.com/v1" maxLength={500} style={inputStyle} />
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>Default Model</label>
            <input type="text" value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)} placeholder="gpt-4o" maxLength={100} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>API Key Secret</label>
            <select value={secretRef} onChange={(e) => setSecretRef(e.target.value)} style={inputStyle}>
              <option value="">None</option>
              {secrets.map((s) => <option key={s.id} value={s.name}>{s.name} ({s.masked_display})</option>)}
            </select>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>Select a secret from your workspace</span>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Description</label>
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" maxLength={2000} style={inputStyle} />
        </div>

        {error && <p style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8 }}>
          <button type="submit" disabled={isPending} style={{
            ...primaryButtonStyle, cursor: isPending ? 'not-allowed' : 'pointer', opacity: isPending ? 0.7 : 1,
          }}>
            {isPending ? 'Creating...' : 'Create Integration'}
          </button>
          <button type="button" onClick={onCancel} style={secondaryButtonStyle}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
