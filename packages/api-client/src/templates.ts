import type { ApiClient } from './client';
import type { TaskTemplate, AgentTemplate } from '@keviq/domain-types';

export interface TemplatesApi {
  listTaskTemplates: (category?: string) => Promise<{ items: TaskTemplate[]; count: number }>;
  getTaskTemplate: (templateId: string) => Promise<TaskTemplate>;
  listAgentTemplates: () => Promise<{ items: AgentTemplate[]; count: number }>;
  getAgentTemplate: (templateId: string) => Promise<AgentTemplate>;
}

export function createTemplatesApi(client: ApiClient): TemplatesApi {
  return {
    listTaskTemplates: (category) => {
      const params = category ? `?category=${encodeURIComponent(category)}` : '';
      return client.get(`/v1/task-templates${params}`);
    },
    getTaskTemplate: (templateId) =>
      client.get(`/v1/task-templates/${encodeURIComponent(templateId)}`),
    listAgentTemplates: () => client.get('/v1/agent-templates'),
    getAgentTemplate: (templateId) =>
      client.get(`/v1/agent-templates/${encodeURIComponent(templateId)}`),
  };
}
