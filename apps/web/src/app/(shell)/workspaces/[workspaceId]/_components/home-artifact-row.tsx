import Link from 'next/link';
import type { Artifact } from '@keviq/domain-types';
import { artifactDetailPath } from '@keviq/routing';
import { formatRelativeTime, formatArtifactType } from '@/modules/shared/format-utils';

const rowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '8px 0',
  borderBottom: '1px solid #f3f4f6',
};

const typeBadge: React.CSSProperties = {
  display: 'inline-block',
  padding: '1px 6px',
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 500,
  backgroundColor: '#f3f4f6',
  color: '#6b7280',
};

interface Props {
  artifact: Artifact;
  workspaceId: string;
}

export function HomeArtifactRow({ artifact, workspaceId }: Props) {
  return (
    <div style={rowStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link
          href={artifactDetailPath(workspaceId, artifact.id)}
          style={{ fontSize: 13, color: '#1d4ed8', textDecoration: 'none' }}
        >
          {artifact.name.length > 40 ? artifact.name.slice(0, 40) + '…' : artifact.name}
        </Link>
        <span style={typeBadge}>{formatArtifactType(artifact.artifact_type)}</span>
      </div>
      <span style={{ fontSize: 11, color: '#9ca3af' }}>
        {formatRelativeTime(artifact.created_at)}
      </span>
    </div>
  );
}
