'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createApiClient, createAuthApi, ApiClientError } from '@keviq/api-client';
import { AuthCard, inputStyle, SubmitButton } from '@/modules/auth/auth-card';
import { setAuthCookie } from '@/modules/auth/cookie';
import Link from 'next/link';
import { LogoBrand } from '@/modules/brand/logo-brand';

const client = createApiClient('');
const authApi = createAuthApi(client);

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justRegistered = searchParams.get('registered') === '1';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const session = await authApi.login(email, password);
      setAuthCookie(session.access_token);
      router.push('/');
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 401) {
        setError('Invalid email or password.');
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard>
      <div style={{ marginBottom: 24 }}>
        <LogoBrand size="lg" showSlogan animated />
      </div>
      <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 16, textAlign: 'center' }}>
        Sign in to your account
      </p>

      {justRegistered && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: 6,
            marginBottom: 16,
            fontSize: 14,
            color: '#166534',
          }}
        >
          Account created successfully. Please sign in.
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 14, marginBottom: 4 }}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'block', fontSize: 14, marginBottom: 4 }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={inputStyle}
          />
        </div>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 16 }}>{error}</p>
        )}

        <div style={{ marginBottom: 16 }}>
          <SubmitButton loading={loading} label="Sign In" loadingLabel="Signing in..." />
        </div>
      </form>

      <p style={{ fontSize: 14, color: '#6b7280', textAlign: 'center' }}>
        Don&apos;t have an account?{' '}
        <Link href="/register" style={{ color: '#1d4ed8', textDecoration: 'none' }}>
          Create one
        </Link>
      </p>
    </AuthCard>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthCard><p>Loading...</p></AuthCard>}>
      <LoginForm />
    </Suspense>
  );
}
