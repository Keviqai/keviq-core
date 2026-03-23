'use client';

import { useState } from 'react';
import type { ToolApprovalContext } from '@keviq/domain-types';

/**
 * Tool approval action panel — shows tool context + 4 action buttons.
 *
 * Displayed on approval detail page when target_type === 'tool_call'.
 * Actions: Approve (dispatch real tool), Reject (fail invocation),
 * Override (inject synthetic result), Cancel (terminate invocation).
 */

interface ToolApprovalPanelProps {
  toolContext: ToolApprovalContext;
  isPending: boolean;
  onDecide: (decision: 'approve' | 'reject' | 'override' | 'cancel', comment?: string, overrideOutput?: string) => Promise<void>;
  isSubmitting: boolean;
  error?: string | null;
}

export function ToolApprovalPanel({ toolContext, isPending, onDecide, isSubmitting, error }: ToolApprovalPanelProps) {
  const [comment, setComment] = useState('');
  const [overrideOutput, setOverrideOutput] = useState('');
  const [showOverrideInput, setShowOverrideInput] = useState(false);

  if (!isPending) return null;

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
      {/* Tool context card */}
      <div style={{
        backgroundColor: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 6,
        padding: 12, marginBottom: 16,
      }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, color: '#92400e', marginBottom: 8, marginTop: 0 }}>
          Tool Awaiting Approval
        </h4>
        <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '100px 1fr', gap: '4px 12px', fontSize: 13 }}>
          <dt style={{ color: '#92400e', fontWeight: 500 }}>Tool</dt>
          <dd style={{ margin: 0, fontFamily: 'monospace', color: '#78350f' }}>{toolContext.tool_name}</dd>
          <dt style={{ color: '#92400e', fontWeight: 500 }}>Risk</dt>
          <dd style={{ margin: 0, color: '#78350f' }}>{toolContext.risk_reason}</dd>
          {toolContext.arguments_preview && (
            <>
              <dt style={{ color: '#92400e', fontWeight: 500 }}>Arguments</dt>
              <dd style={{
                margin: 0, fontFamily: 'monospace', fontSize: 12, color: '#78350f',
                whiteSpace: 'pre-wrap', maxHeight: 120, overflow: 'auto',
                backgroundColor: '#fffbeb', padding: 4, borderRadius: 4,
              }}>
                {toolContext.arguments_preview.slice(0, 500)}
                {toolContext.arguments_preview.length > 500 ? '...' : ''}
              </dd>
            </>
          )}
        </dl>
      </div>

      {/* Comment input */}
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional comment..."
        rows={2}
        style={{
          width: '100%', padding: 10, fontSize: 14, borderRadius: 6,
          border: '1px solid #d1d5db', marginBottom: 12, resize: 'vertical',
          boxSizing: 'border-box',
        }}
      />

      {/* Override input (expandable) */}
      {showOverrideInput && (
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
            Override output (synthetic tool result):
          </label>
          <textarea
            value={overrideOutput}
            onChange={(e) => setOverrideOutput(e.target.value)}
            placeholder="Enter the output the model should receive instead of running the tool..."
            rows={4}
            maxLength={32768}
            style={{
              width: '100%', padding: 10, fontSize: 13, fontFamily: 'monospace',
              borderRadius: 6, border: '1px solid #d1d5db', resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />
          <p style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
            {overrideOutput.length}/32768 chars
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          onClick={() => onDecide('approve', comment || undefined)}
          disabled={isSubmitting}
          style={{
            padding: '8px 18px', borderRadius: 6, border: 'none', cursor: 'pointer',
            backgroundColor: '#059669', color: '#fff', fontWeight: 600, fontSize: 13,
            opacity: isSubmitting ? 0.6 : 1,
          }}
        >
          Approve
        </button>
        <button
          onClick={() => onDecide('reject', comment || undefined)}
          disabled={isSubmitting}
          style={{
            padding: '8px 18px', borderRadius: 6, border: 'none', cursor: 'pointer',
            backgroundColor: '#dc2626', color: '#fff', fontWeight: 600, fontSize: 13,
            opacity: isSubmitting ? 0.6 : 1,
          }}
        >
          Reject
        </button>
        {!showOverrideInput ? (
          <button
            onClick={() => setShowOverrideInput(true)}
            disabled={isSubmitting}
            style={{
              padding: '8px 18px', borderRadius: 6, border: '1px solid #6366f1', cursor: 'pointer',
              backgroundColor: '#fff', color: '#6366f1', fontWeight: 600, fontSize: 13,
              opacity: isSubmitting ? 0.6 : 1,
            }}
          >
            Override...
          </button>
        ) : (
          <button
            onClick={() => onDecide('override', comment || undefined, overrideOutput)}
            disabled={isSubmitting || !overrideOutput.trim()}
            style={{
              padding: '8px 18px', borderRadius: 6, border: 'none', cursor: 'pointer',
              backgroundColor: '#6366f1', color: '#fff', fontWeight: 600, fontSize: 13,
              opacity: (isSubmitting || !overrideOutput.trim()) ? 0.6 : 1,
            }}
          >
            Submit Override
          </button>
        )}
        <button
          onClick={() => onDecide('cancel', comment || undefined)}
          disabled={isSubmitting}
          style={{
            padding: '8px 18px', borderRadius: 6, border: '1px solid #6b7280', cursor: 'pointer',
            backgroundColor: '#fff', color: '#6b7280', fontWeight: 600, fontSize: 13,
            opacity: isSubmitting ? 0.6 : 1,
          }}
        >
          Cancel
        </button>
      </div>

      {error && (
        <p style={{ color: '#991b1b', fontSize: 13, marginTop: 8 }}>
          Error: {error}
        </p>
      )}
    </div>
  );
}
