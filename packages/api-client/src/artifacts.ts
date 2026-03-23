import type { ApiClient } from './client';
import type { Artifact, ArtifactAnnotation, ArtifactProvenance, LineageEdge } from '@keviq/domain-types';

export interface ArtifactLineageResponse {
  artifact_id: string;
  ancestors: LineageEdge[];
  count: number;
}

export interface ArtifactPreviewResponse {
  artifact_id: string;
  mime_type: string | null;
  preview_kind: 'text' | 'json' | 'markdown' | 'unsupported' | 'too_large' | 'unavailable';
  size_bytes: number | null;
  truncated: boolean;
  content: string | null;
}

export interface ArtifactUploadResponse {
  id: string;
  name: string;
  artifact_type: string;
  root_type: string;
  artifact_status: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum: string | null;
  workspace_id: string;
  created_at: string | null;
  uploader_user_id: string;
  original_filename: string;
}

export interface ArtifactsApi {
  list: (workspaceId: string) => Promise<{ items: Artifact[]; count: number; limit: number }>;
  get: (workspaceId: string, artifactId: string) => Promise<Artifact>;
  listByRun: (workspaceId: string, runId: string) => Promise<{ items: Artifact[]; count: number; limit: number }>;
  provenance: (workspaceId: string, artifactId: string) => Promise<ArtifactProvenance>;
  lineageAncestors: (workspaceId: string, artifactId: string) => Promise<ArtifactLineageResponse>;
  preview: (workspaceId: string, artifactId: string) => Promise<ArtifactPreviewResponse>;
  upload: (workspaceId: string, file: File, artifactName?: string) => Promise<ArtifactUploadResponse>;
  downloadUrl: (workspaceId: string, artifactId: string) => string;
  listAnnotations: (workspaceId: string, artifactId: string) => Promise<{ items: ArtifactAnnotation[]; count: number }>;
  createAnnotation: (workspaceId: string, artifactId: string, body: string) => Promise<ArtifactAnnotation>;
}

export function createArtifactsApi(client: ApiClient): ArtifactsApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts`),
    get: (workspaceId, artifactId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}`),
    listByRun: (workspaceId, runId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}/artifacts`),
    provenance: (workspaceId, artifactId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/provenance`),
    lineageAncestors: (workspaceId, artifactId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/lineage/ancestors`),
    preview: (workspaceId, artifactId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/preview`),
    upload: (workspaceId, file, artifactName) => {
      const formData = new FormData();
      formData.append('file', file);
      const params = new URLSearchParams();
      if (artifactName) params.set('artifact_name', artifactName);
      const qs = params.toString();
      return client.postForm(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/upload${qs ? `?${qs}` : ''}`,
        formData,
      );
    },
    downloadUrl: (workspaceId, artifactId) =>
      `/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/download`,
    listAnnotations: (workspaceId, artifactId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/annotations`),
    createAnnotation: (workspaceId, artifactId, body) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/annotations`, { body }),
  };
}
