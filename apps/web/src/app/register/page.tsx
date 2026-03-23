'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createApiClient, createAuthApi, ApiClientError } from '@keviq/api-client';
import { loginPath } from '@keviq/routing';
import { AuthCard, inputStyle, SubmitButton } from '@/modules/auth/auth-card';
import Link from 'next/link';
import { LogoBrand } from '@/modules/brand/logo-brand';

const client = createApiClient('');
const authApi = createAuthApi(client);

export default function RegisterPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setLoading(true);
    try {
      await authApi.register(email, displayName.trim(), password);
      router.push(loginPath({ registered: true }));
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        setError('An account with this email already exists.');
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
        Create your account
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 14, marginBottom: 4 }}>
            Display name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            maxLength={200}
            style={inputStyle}
          />
        </div>

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
            minLength={8}
            style={inputStyle}
          />
          <span style={{ fontSize: 12, color: '#9ca3af' }}>At least 8 characters</span>
        </div>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 16 }}>{error}</p>
        )}

        <div style={{ marginBottom: 16 }}>
          <SubmitButton loading={loading} label="Create Account" loadingLabel="Creating account..." />
        </div>
      </form>

      <p style={{ fontSize: 14, color: '#6b7280', textAlign: 'center' }}>
        Already have an account?{' '}
        <Link href="/login" style={{ color: '#1d4ed8', textDecoration: 'none' }}>
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
