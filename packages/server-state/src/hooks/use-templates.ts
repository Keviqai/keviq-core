'use client';

import { useQuery } from '@tanstack/react-query';
import { createTemplatesApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const templatesApi = createTemplatesApi(apiClient);

export function useTaskTemplates(category?: string) {
  return useQuery({
    queryKey: queryKeys.taskTemplates.list(category),
    queryFn: () => templatesApi.listTaskTemplates(category),
    staleTime: 5 * 60 * 1000, // 5 minutes — templates rarely change
  });
}

export function useAgentTemplates() {
  return useQuery({
    queryKey: queryKeys.agentTemplates.list,
    queryFn: () => templatesApi.listAgentTemplates(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTaskTemplate(templateId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.taskTemplates.detail(templateId ?? ''),
    queryFn: () => templatesApi.getTaskTemplate(templateId!),
    enabled: !!templateId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAgentTemplate(templateId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.agentTemplates.detail(templateId ?? ''),
    queryFn: () => templatesApi.getAgentTemplate(templateId!),
    enabled: !!templateId,
    staleTime: 5 * 60 * 1000,
  });
}
