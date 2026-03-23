'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createArtifactsApi } from '@keviq/api-client';
import type { ArtifactAnnotation } from '@keviq/domain-types';
import type { ArtifactUploadResponse } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const artifactsApi = createArtifactsApi(apiClient);

export function useArtifactList(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.list(workspaceId),
    queryFn: () => artifactsApi.list(workspaceId),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });
}

export function useArtifact(workspaceId: string, artifactId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.detail(workspaceId, artifactId),
    queryFn: () => artifactsApi.get(workspaceId, artifactId),
    enabled: !!workspaceId && !!artifactId,
    staleTime: 30_000,
  });
}

export function useArtifactsByRun(workspaceId: string, runId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.listByRun(workspaceId, runId),
    queryFn: () => artifactsApi.listByRun(workspaceId, runId),
    enabled: !!workspaceId && !!runId,
    staleTime: 30_000,
  });
}

export function useArtifactProvenance(workspaceId: string, artifactId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.provenance(workspaceId, artifactId),
    queryFn: () => artifactsApi.provenance(workspaceId, artifactId),
    enabled: !!workspaceId && !!artifactId,
    staleTime: 60_000,
  });
}

export function useArtifactLineage(workspaceId: string, artifactId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.lineage(workspaceId, artifactId),
    queryFn: () => artifactsApi.lineageAncestors(workspaceId, artifactId),
    enabled: !!workspaceId && !!artifactId,
    staleTime: 60_000,
  });
}

export function useArtifactPreview(workspaceId: string, artifactId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.preview(workspaceId, artifactId),
    queryFn: () => artifactsApi.preview(workspaceId, artifactId),
    enabled: !!workspaceId && !!artifactId,
    staleTime: 60_000,
  });
}

export function useArtifactDownloadUrl(workspaceId: string, artifactId: string): string {
  return artifactsApi.downloadUrl(workspaceId, artifactId);
}

export function useArtifactUpload(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation<ArtifactUploadResponse, Error, { file: File; artifactName?: string }>({
    mutationFn: ({ file, artifactName }) =>
      artifactsApi.upload(workspaceId, file, artifactName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.artifacts.list(workspaceId) });
    },
  });
}

export function useArtifactAnnotations(workspaceId: string, artifactId: string) {
  return useQuery({
    queryKey: queryKeys.artifacts.annotations(workspaceId, artifactId),
    queryFn: () => artifactsApi.listAnnotations(workspaceId, artifactId),
    enabled: !!workspaceId && !!artifactId,
    staleTime: 30_000,
  });
}

export function useCreateAnnotation(workspaceId: string, artifactId: string) {
  const qc = useQueryClient();
  return useMutation<ArtifactAnnotation, Error, { body: string }>({
    mutationFn: ({ body }) => artifactsApi.createAnnotation(workspaceId, artifactId, body),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.artifacts.annotations(workspaceId, artifactId),
      });
    },
  });
}
