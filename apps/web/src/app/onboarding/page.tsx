'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth, useWorkspaces, useCreateWorkspace } from '@keviq/server-state';
import { workspacePath } from '@keviq/routing';
import { ApiClientError } from '@keviq/api-client';
import { AuthCard, inputStyle, SubmitButton } from '@/modules/auth/auth-card';
import { clearAuthCookie } from '@/modules/auth/cookie';
import { LogoBrand } from '@/modules/brand/logo-brand';

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);
}

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: authData, isLoading: authLoading } = useAuth();
  const { data: workspaces, isLoading: wsLoading } = useWorkspaces();
  const createWorkspace = useCreateWorkspace();

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If user already has workspaces, redirect to the first one
  useEffect(() => {
    if (!authLoading && !wsLoading && workspaces && workspaces.length > 0) {
      router.replace(workspacePath(workspaces[0].id));
    }
  }, [authLoading, wsLoading, workspaces, router]);

  function handleNameChange(value: string) {
    setName(value);
    if (!slugTouched) {
      setSlug(toSlug(value));
    }
  }

  function handleSlugChange(value: string) {
    setSlugTouched(true);
    setSlug(value.toLowerCase().replace(/[^a-z0-9-]/g, ''));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const finalSlug = slug || toSlug(name.trim());
    if (!finalSlug) {
      setError('Please enter a workspace name.');
      return;
    }

    createWorkspace.mutate(
      { slug: finalSlug, displayName: name.trim() },
      {
        onSuccess: (workspace) => {
          router.push(workspacePath(workspace.id));
        },
        onError: (err) => {
          if (err instanceof ApiClientError && err.status === 409) {
            setError('This slug is already taken. Please choose a different name.');
          } else {
            setError('Failed to create workspace.');
          }
        },
      },
    );
  }

  function handleLogout() {
    clearAuthCookie();
    queryClient.clear();
    router.push('/login');
  }

  if (authLoading || wsLoading) {
    return (
      <AuthCard>
        <p>Loading...</p>
      </AuthCard>
    );
  }

  // Already handled by useEffect redirect above
  if (workspaces && workspaces.length > 0) {
    return (
      <AuthCard>
        <p>Redirecting...</p>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
        <LogoBrand size="md" />
        <button
          onClick={handleLogout}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 13,
            color: '#6b7280',
            cursor: 'pointer',
            padding: '4px 8px',
          }}
        >
          Sign out
        </button>
      </div>

      {authData?.user && (
        <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 8 }}>
          Welcome, {authData.user.display_name}
        </p>
      )}

      <div
        style={{
          padding: '14px 16px',
          backgroundColor: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: 8,
          marginBottom: 24,
        }}
      >
        <p style={{ fontSize: 14, color: '#0c4a6e', fontWeight: 600, marginBottom: 4 }}>
          Create your first workspace
        </p>
        <p style={{ fontSize: 13, color: '#0369a1' }}>
          A workspace is where your team collaborates on tasks, runs, and artifacts.
        </p>
      </div>

      {/* ── Q1 Guidance ── */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#111827' }}>
          What can you delegate to Keviq Core?
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <GuidanceCard
            title="Research Brief"
            text="Research a topic, gather sources, and produce a structured brief with key findings."
          />
          <GuidanceCard
            title="Ops Case Prep"
            text="Prepare case documentation with evidence, checklists, and recommendations."
          />
          <GuidanceCard
            title="Data Analysis"
            text="Analyze data, extract insights, and produce a report with actionable recommendations."
          />
        </div>
        <div style={{
          marginTop: 12,
          padding: '10px 14px',
          backgroundColor: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: 6,
          fontSize: 12,
          color: '#92400e',
          lineHeight: 1.5,
        }}>
          <strong>Keep in mind:</strong> Keviq Core works best for structured knowledge work with clear outputs.
          It is not designed for real-time decisions or handling sensitive data without policy configuration.
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 14, marginBottom: 4 }}>
            Workspace name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="My Team"
            required
            maxLength={200}
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'block', fontSize: 14, marginBottom: 4 }}>Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) => handleSlugChange(e.target.value)}
            placeholder="my-team"
            required
            pattern="^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"
            style={inputStyle}
          />
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            Lowercase letters, numbers, and hyphens only
          </span>
        </div>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 16 }}>{error}</p>
        )}

        <SubmitButton
          loading={createWorkspace.isPending}
          label="Create Workspace"
          loadingLabel="Creating..."
        />
      </form>
    </AuthCard>
  );
}

function GuidanceCard({ title, text }: { title: string; text: string }) {
  return (
    <div style={{
      padding: '10px 14px',
      border: '1px solid #e5e7eb',
      borderRadius: 6,
      backgroundColor: '#fff',
    }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{title}</span>
      <p style={{ fontSize: 12, color: '#6b7280', margin: 0, marginTop: 2 }}>{text}</p>
    </div>
  );
}
