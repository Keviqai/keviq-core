'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { membersPath, policiesPath, secretsPath, integrationsPath, workspacePath } from '@keviq/routing';

const cardStyle = {
  display: 'block' as const,
  padding: 16,
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  textDecoration: 'none' as const,
  color: '#374151',
};

const SECTIONS = [
  { label: 'Members', desc: 'Manage workspace members, invite new users, and update roles.', path: membersPath },
  { label: 'Policies', desc: 'Define permission policies and access control rules.', path: policiesPath },
  { label: 'Secrets', desc: 'Manage API keys, tokens, and credentials for integrations.', path: secretsPath },
  { label: 'Integrations', desc: 'Connect LLM providers and external services to your workspace.', path: integrationsPath },
];

export default function SettingsPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link
          href={workspacePath(workspaceId)}
          style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}
        >
          &larr; Workspace
        </Link>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Settings</h1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 480 }}>
        {SECTIONS.map((s) => (
          <Link key={s.label} href={s.path(workspaceId)} style={cardStyle}>
            <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, marginBottom: 4 }}>{s.label}</h3>
            <p style={{ margin: 0, fontSize: 13, color: '#6b7280' }}>{s.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
