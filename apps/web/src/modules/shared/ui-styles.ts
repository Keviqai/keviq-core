/**
 * Shared UI style constants — plain objects, NOT a component library.
 * Consolidates the 8 most-duplicated inline style patterns across pages.
 */

import type { CSSProperties } from 'react';

// ── Error display ────────────────────────────────────────────

export const errorBoxStyle: CSSProperties = {
  padding: 16,
  backgroundColor: '#fef2f2',
  borderRadius: 8,
  border: '1px solid #fecaca',
};

export const errorTitleStyle: CSSProperties = {
  color: '#991b1b',
  fontWeight: 600,
  marginBottom: 4,
};

export const errorBodyStyle: CSSProperties = {
  color: '#b91c1c',
  fontSize: 13,
  margin: 0,
};

// ── Loading ──────────────────────────────────────────────────

export const loadingTextStyle: CSSProperties = {
  color: '#6b7280',
};

// ── Empty state ──────────────────────────────────────────────

export const emptyStateBoxStyle: CSSProperties = {
  padding: 32,
  textAlign: 'center',
  border: '1px dashed #d1d5db',
  borderRadius: 8,
};

// ── Form elements ────────────────────────────────────────────

export const inputStyle: CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 14,
  boxSizing: 'border-box',
};

export const labelStyle: CSSProperties = {
  display: 'block',
  fontSize: 13,
  marginBottom: 4,
  fontWeight: 500,
};

// ── Buttons ──────────────────────────────────────────────────

export const primaryButtonStyle: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 6,
  border: 'none',
  cursor: 'pointer',
  backgroundColor: '#2563eb',
  color: '#fff',
  fontWeight: 600,
  fontSize: 13,
};

export const secondaryButtonStyle: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  cursor: 'pointer',
  backgroundColor: '#fff',
  color: '#374151',
  fontWeight: 500,
  fontSize: 13,
};
