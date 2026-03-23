export interface ApiMeta {
  request_id: string;
  workspace_id?: string;
  api_version: string;
  timestamp: string;
}

export interface ApiError {
  error_code: string;
  message: string;
  details: unknown[];
  retryable: boolean;
  conflict_with_state: string | null;
  correlation_id: string | null;
}

export interface ApiResponse<T> {
  data: T | null;
  meta: ApiMeta;
  error: ApiError | null;
}

export interface CommandAccepted {
  accepted: boolean;
  resource_type: string;
  resource_id: string;
  current_status: string;
  correlation_id: string;
}

export interface PaginatedList<T> {
  items: T[];
  count: number;
  limit: number;
}
