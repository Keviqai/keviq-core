import type { ApiClient } from './client';
import type { ActivityResponse } from '@keviq/domain-types';

export interface ActivityQueryParams {
  event_type?: string;
  after?: string;
  before?: string;
  limit?: number;
  offset?: number;
}

export interface ActivityApi {
  list: (workspaceId: string, params?: ActivityQueryParams) => Promise<ActivityResponse>;
}

export function createActivityApi(client: ApiClient): ActivityApi {
  return {
    list: (workspaceId, params) => {
      const qs = new URLSearchParams();
      if (params?.event_type) qs.set('event_type', params.event_type);
      if (params?.after) qs.set('after', params.after);
      if (params?.before) qs.set('before', params.before);
      if (params?.limit !== undefined) qs.set('limit', String(params.limit));
      if (params?.offset !== undefined) qs.set('offset', String(params.offset));
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/activity${suffix}`);
    },
  };
}
