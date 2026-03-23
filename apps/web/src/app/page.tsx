'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, useWorkspaces } from '@keviq/server-state';
import { workspacePath } from '@keviq/routing';
import { clearAuthCookie } from '@/modules/auth/cookie';

export default function Home() {
  const router = useRouter();
  const { data: authData, isLoading: authLoading, isError: authError } = useAuth();
  const { data: workspacesData, isLoading: wsLoading } = useWorkspaces();

  useEffect(() => {
    if (authLoading || wsLoading) return;

    if (authError || !authData) {
      clearAuthCookie();
      router.replace('/login');
      return;
    }

    // Use workspace list from workspace-service (not auth/me which doesn't include workspaces)
    const workspaces = workspacesData ?? [];
    if (workspaces.length > 0) {
      router.replace(workspacePath(workspaces[0].id));
    } else {
      router.replace('/onboarding');
    }
  }, [authData, authLoading, authError, workspacesData, wsLoading, router]);

  return (
    <main style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <p>Loading...</p>
    </main>
  );
}
