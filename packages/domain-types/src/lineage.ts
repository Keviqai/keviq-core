export type EdgeType =
  | 'derived_from'
  | 'transformed_from'
  | 'aggregated_from'
  | 'promoted_from';

export interface LineageEdge {
  id: string;
  child_artifact_id: string;
  parent_artifact_id: string;
  edge_type: EdgeType;
  run_id: string | null;
  step_id: string | null;
  created_at: string;
}
