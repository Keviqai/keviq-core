# Artifact Search, Filter, and Tagging

> How to query, filter, sort, and tag artifacts in Keviq Core.

## Overview

The artifact-service provides search and filtering capabilities on the
artifact list endpoint, plus a tagging system for user-defined labels. All
endpoints are accessible through the api-gateway with workspace-scoped
authorization.

## Filter Parameters

### GET /api/v1/workspaces/{workspace_id}/artifacts

All filter parameters are optional query strings. When multiple filters are
provided, they are combined with AND logic.

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `name_contains` | string | Case-insensitive substring match on artifact name | `?name_contains=report` |
| `artifact_type` | string | Exact match on artifact type | `?artifact_type=document` |
| `artifact_status` | string | Exact match on status | `?artifact_status=finalized` |
| `root_type` | string | Filter by root type (task, run, manual) | `?root_type=task` |
| `mime_type` | string | Exact match on MIME type | `?mime_type=text/plain` |
| `created_after` | ISO 8601 datetime | Artifacts created after this timestamp | `?created_after=2026-03-01T00:00:00Z` |
| `created_before` | ISO 8601 datetime | Artifacts created before this timestamp | `?created_before=2026-03-31T23:59:59Z` |
| `tag` | string | Artifacts that have this tag (repeatable) | `?tag=reviewed&tag=final` |

### Combining Filters

```
GET /api/v1/workspaces/{wid}/artifacts?artifact_type=document&artifact_status=finalized&tag=reviewed&created_after=2026-03-01T00:00:00Z
```

This returns finalized documents tagged "reviewed" created after March 1st.

When multiple `tag` parameters are provided, artifacts must have ALL specified
tags (AND logic).

## Sort Options

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_by` | string | `created_at` | Field to sort on |
| `sort_order` | string | `desc` | Sort direction: `asc` or `desc` |

### Sortable Fields

| Field | Description |
|-------|-------------|
| `created_at` | Artifact creation timestamp (default) |
| `name` | Artifact name (alphabetical) |
| `size_bytes` | Artifact size |

### Example

```
GET /api/v1/workspaces/{wid}/artifacts?sort_by=size_bytes&sort_order=desc
```

Returns artifacts sorted by size, largest first.

## Pagination

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max items per page (1-200) |
| `offset` | integer | 0 | Number of items to skip |

Response includes pagination metadata:

```json
{
  "items": [...],
  "total": 142,
  "limit": 50,
  "offset": 0
}
```

## Tagging

Tags are free-form string labels attached to artifacts. They enable
user-defined categorization beyond the built-in type and status fields.

### Tag Constraints

| Constraint | Value |
|------------|-------|
| Max length | 64 characters |
| Allowed characters | alphanumeric, hyphens, underscores |
| Max tags per artifact | 20 |
| Case sensitivity | Tags are stored lowercase |

### Add Tags

```
POST /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/tags
Content-Type: application/json

{
  "tags": ["reviewed", "q1-deliverable"]
}
```

**Response (200):**

```json
{
  "artifact_id": "art-abc123",
  "tags": ["reviewed", "q1-deliverable"]
}
```

Adding a tag that already exists is a no-op (idempotent).

### Remove Tags

```
DELETE /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/tags
Content-Type: application/json

{
  "tags": ["q1-deliverable"]
}
```

**Response (200):**

```json
{
  "artifact_id": "art-abc123",
  "tags": ["reviewed"]
}
```

Removing a tag that does not exist is a no-op.

### List Tags

```
GET /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/tags
```

**Response (200):**

```json
{
  "artifact_id": "art-abc123",
  "tags": ["reviewed"]
}
```

## Gateway Routes

All artifact endpoints are proxied through the api-gateway. The gateway adds
workspace-scoped authorization checks.

| Method | Gateway Route | Permission | Backend Target |
|--------|-------------|------------|----------------|
| GET | `/api/v1/workspaces/{wid}/artifacts` | `workspace:view` | artifact-service |
| GET | `/api/v1/workspaces/{wid}/artifacts/{id}` | `workspace:view` | artifact-service |
| POST | `/api/v1/workspaces/{wid}/artifacts/{id}/tags` | `workspace:edit` | artifact-service |
| DELETE | `/api/v1/workspaces/{wid}/artifacts/{id}/tags` | `workspace:edit` | artifact-service |
| GET | `/api/v1/workspaces/{wid}/artifacts/{id}/tags` | `workspace:view` | artifact-service |

## Frontend Integration

The web frontend uses the `@keviq/api-client` package for artifact queries:

```typescript
import { listArtifacts } from "@keviq/api-client/artifacts";

const result = await listArtifacts(workspaceId, {
  name_contains: "report",
  artifact_status: "finalized",
  tag: ["reviewed"],
  sort_by: "created_at",
  sort_order: "desc",
  limit: 20,
  offset: 0,
});
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Filter returns no results | Verify filter values match stored data exactly (status, type) |
| Tag endpoint returns 404 | Confirm artifact exists and workspace ID is correct |
| Slow queries on large datasets | Check that DB indexes exist on `artifact_type`, `artifact_status`, `created_at` |
| Tag not appearing in filter results | Tags are lowercased on storage; use lowercase in `?tag=` query |
