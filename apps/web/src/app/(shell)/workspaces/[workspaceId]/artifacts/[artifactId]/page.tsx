'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import {
  useArtifact,
  useArtifactProvenance,
  useArtifactLineage,
  useArtifactDownloadUrl,
  useArtifactPreview,
  useTask,
} from '@keviq/server-state';
import { artifactsPath, artifactDetailPath, runDetailPath, taskDetailPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { formatSize, formatArtifactType } from '@/modules/shared/format-utils';
import { ArtifactPreviewSection } from '@/modules/artifact/artifact-preview-section';
import { ProvenanceTrustCard } from '@/modules/artifact/provenance-trust-card';
import { LineageCue } from '@/modules/artifact/lineage-cue';
import { ArtifactDiffView } from '@/modules/artifact/artifact-diff-view';
import { AnnotationPanel } from '@/modules/artifact/annotation-panel';
import { ArtifactExportActions } from '@/modules/artifact/artifact-export-actions';
import { RequestApprovalModal } from '@/modules/approval/request-approval-modal';

export default function ArtifactDetailPage() {
  const params = useParams<{ workspaceId: string; artifactId: string }>();
  const { workspaceId, artifactId } = params;
  const searchParams = useSearchParams();
  const compareId = searchParams.get('compare');
  const [showApprovalModal, setShowApprovalModal] = useState(false);

  // Main artifact data
  const { data: artifact, isLoading, isError, error } = useArtifact(workspaceId, artifactId);
  const { data: provenance, isLoading: provLoading, isError: provError } = useArtifactProvenance(workspaceId, artifactId);
  const { data: lineage, isLoading: linLoading, isError: linError } = useArtifactLineage(workspaceId, artifactId);
  const downloadUrl = useArtifactDownloadUrl(workspaceId, artifactId);

  // Fetch task title for human-friendly links in Details section
  const { data: taskData } = useTask(artifact?.task_id ?? '');
  const taskTitle = taskData?.title;

  // Compare mode data (only fetched when compareId is present)
  const { data: parentArtifact, isLoading: parentLoading, isError: parentError } = useArtifact(workspaceId, compareId ?? '');
  const { data: currentPreview, isLoading: currentPreviewLoading } = useArtifactPreview(workspaceId, compareId ? artifactId : '');
  const { data: parentPreview, isLoading: parentPreviewLoading, isError: parentPreviewError } = useArtifactPreview(workspaceId, compareId ?? '');
  const { data: parentLineage } = useArtifactLineage(workspaceId, compareId ?? '');

  if (isLoading) {
    return <p style={{ color: '#6b7280' }}>Loading artifact...</p>;
  }

  if (isError || !artifact) {
    return (
      <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
        <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load artifact</p>
        <p style={{ color: '#b91c1c', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'Artifact not found or an unexpected error occurred.'}
        </p>
        <Link href={artifactsPath(workspaceId)} style={{ color: '#1d4ed8', fontSize: 13 }}>
          Back to artifacts
        </Link>
      </div>
    );
  }

  const versionNumber = lineage ? lineage.ancestors.length + 1 : null;

  // ── Compare mode ───────────────────────────────────────────────────────────
  if (compareId) {
    const currentVersion = versionNumber ?? '?';
    const parentVersion = versionNumber != null ? versionNumber - 1 : '?';
    const grandparentId = parentLineage?.ancestors[0]?.parent_artifact_id ?? null;
    const olderCompareUrl = grandparentId
      ? `${artifactDetailPath(workspaceId, compareId)}?compare=${grandparentId}`
      : null;

    return (
      <div>
        {/* Back + navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <Link
            href={artifactDetailPath(workspaceId, artifactId)}
            style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}
          >
            &larr; Back to {artifact.name}
          </Link>
          {olderCompareUrl && (
            <Link
              href={olderCompareUrl}
              style={{ fontSize: 13, color: '#1d4ed8', textDecoration: 'none' }}
            >
              &larr; Compare older
            </Link>
          )}
        </div>

        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          Compare versions — {artifact.name}
        </h2>

        {/* Parent loading / error */}
        {parentLoading && <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading parent artifact...</p>}
        {parentError && (
          <p style={{ color: '#b91c1c', fontSize: 13 }}>Could not load parent artifact for comparison.</p>
        )}

        {parentArtifact && (
          <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
            Comparing{' '}
            <Link href={artifactDetailPath(workspaceId, compareId)} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
              {parentArtifact.name}
            </Link>
            {' '}(v{parentVersion}) → current (v{currentVersion})
          </p>
        )}

        {/* Diff view */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <ArtifactDiffView
            currentPreview={currentPreview}
            parentPreview={parentPreview}
            currentVersionLabel={`v${currentVersion}`}
            parentVersionLabel={`v${parentVersion}`}
            isLoading={currentPreviewLoading || parentPreviewLoading}
            isError={parentPreviewError}
          />
        </div>
      </div>
    );
  }

  // ── Normal detail mode ─────────────────────────────────────────────────────
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={artifactsPath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Outputs
        </Link>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>{artifact.name}</h1>
        {versionNumber !== null && versionNumber > 1 && (
          <span style={{
            fontSize: 12, padding: '2px 8px',
            backgroundColor: '#fef3c7', color: '#92400e',
            borderRadius: 4, fontWeight: 700,
          }}>
            v{versionNumber}
          </span>
        )}
        {artifact.artifact_status === 'ready' && (
          <>
            <a
              href={downloadUrl}
              download
              style={{
                padding: '6px 16px', backgroundColor: '#1d4ed8', color: '#fff',
                borderRadius: 6, textDecoration: 'none', fontSize: 13, fontWeight: 500,
              }}
            >
              Download
            </a>
            <button
              onClick={() => setShowApprovalModal(true)}
              style={{
                padding: '6px 16px', backgroundColor: '#fff', color: '#374151',
                border: '1px solid #d1d5db', borderRadius: 6, cursor: 'pointer',
                fontSize: 13, fontWeight: 500,
              }}
            >
              Request Approval
            </button>
          </>
        )}
        <ArtifactExportActions
          workspaceId={workspaceId}
          artifactId={artifactId}
          artifactName={artifact.name}
          artifactStatus={artifact.artifact_status}
        />
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 24, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Status</span>
          <div style={{ marginTop: 2 }}><StatusBadge status={artifact.artifact_status} /></div>
        </div>
        <div>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Type</span>
          <p style={{ margin: 0, marginTop: 2 }}>{formatArtifactType(artifact.artifact_type)}</p>
        </div>
        <div>
          <span style={{ fontSize: 12, color: '#6b7280' }}>MIME</span>
          <p style={{ margin: 0, marginTop: 2 }}>{artifact.mime_type ?? '—'}</p>
        </div>
        <div>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Size</span>
          <p style={{ margin: 0, marginTop: 2 }}>{formatSize(artifact.size_bytes)}</p>
        </div>
        <div>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Root Type</span>
          <p style={{ margin: 0, marginTop: 2 }}>{artifact.root_type}</p>
        </div>
      </div>

      {/* Preview */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Preview</h3>
        <ArtifactPreviewSection
          workspaceId={workspaceId}
          artifactId={artifactId}
          isReady={artifact.artifact_status === 'ready'}
        />
      </div>

      {/* Provenance */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Provenance</h3>
        <ProvenanceTrustCard provenance={provenance} isLoading={provLoading} isError={provError} />
      </div>

      {/* Lineage */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Lineage</h3>
        <LineageCue
          lineage={lineage}
          isLoading={linLoading}
          isError={linError}
          workspaceId={workspaceId}
          artifactId={artifactId}
        />
      </div>

      {/* Annotations */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Annotations</h3>
        <AnnotationPanel workspaceId={workspaceId} artifactId={artifactId} />
      </div>

      {/* Details */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Details</h3>
        <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '6px 16px', margin: 0, fontSize: 13 }}>
          <dt style={{ color: '#6b7280' }}>Artifact ID</dt>
          <dd style={{ margin: 0, fontFamily: 'monospace' }}>{artifact.id}</dd>
          <dt style={{ color: '#6b7280' }}>Run</dt>
          <dd style={{ margin: 0 }}>
            <Link href={runDetailPath(workspaceId, artifact.run_id)} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
              {taskTitle ? `Run — ${taskTitle}` : `${artifact.run_id.slice(0, 8)}...`}
            </Link>
          </dd>
          <dt style={{ color: '#6b7280' }}>Task</dt>
          <dd style={{ margin: 0 }}>
            <Link href={taskDetailPath(workspaceId, artifact.task_id)} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
              {taskTitle ?? `${artifact.task_id.slice(0, 8)}...`}
            </Link>
          </dd>
          {artifact.step_id && (
            <>
              <dt style={{ color: '#6b7280' }}>Step</dt>
              <dd style={{ margin: 0, fontFamily: 'monospace' }}>{artifact.step_id.slice(0, 8)}...</dd>
            </>
          )}
          {artifact.checksum && (
            <>
              <dt style={{ color: '#6b7280' }}>Checksum (SHA-256)</dt>
              <dd style={{ margin: 0, fontFamily: 'monospace', wordBreak: 'break-all' }}>{artifact.checksum}</dd>
            </>
          )}
          <dt style={{ color: '#6b7280' }}>Created</dt>
          <dd style={{ margin: 0 }}>{new Date(artifact.created_at).toLocaleString()}</dd>
          <dt style={{ color: '#6b7280' }}>Updated</dt>
          <dd style={{ margin: 0 }}>{new Date(artifact.updated_at).toLocaleString()}</dd>
          {artifact.ready_at && (
            <>
              <dt style={{ color: '#6b7280' }}>Ready</dt>
              <dd style={{ margin: 0 }}>{new Date(artifact.ready_at).toLocaleString()}</dd>
            </>
          )}
          {artifact.failed_at && (
            <>
              <dt style={{ color: '#6b7280' }}>Failed</dt>
              <dd style={{ margin: 0, color: '#991b1b' }}>{new Date(artifact.failed_at).toLocaleString()}</dd>
            </>
          )}
        </dl>
      </div>

      {showApprovalModal && (
        <RequestApprovalModal
          workspaceId={workspaceId}
          artifactId={artifactId}
          artifactName={artifact.name}
          onClose={() => setShowApprovalModal(false)}
        />
      )}
    </div>
  );
}
