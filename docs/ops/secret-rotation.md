# Secret Key Rotation

> How Keviq Core manages versioned encryption keys and rotates secrets without
> downtime.

## Overview

The secret-broker service encrypts workspace secrets at rest using versioned
symmetric keys. The rotation design allows operators to introduce a new key
version, re-encrypt all secrets, and retire old keys -- all without service
interruption.

## Key Versioning Scheme

Encryption keys are supplied as environment variables with a version suffix:

```
SECRET_ENCRYPTION_KEY_V1=base64-encoded-key-here
SECRET_ENCRYPTION_KEY_V2=base64-encoded-key-here
```

### Rules

1. Keys must follow the naming pattern `SECRET_ENCRYPTION_KEY_V<N>` where N
   is a positive integer.
2. The **highest version** is always used for new encryptions.
3. All loaded versions remain available for **decryption** of existing secrets.
4. There is no upper limit on the number of versions, but only the two most
   recent should be active in steady state.

## KeyRegistry

The `KeyRegistry` class (`apps/secret-broker/src/infrastructure/key_registry.py`)
loads keys at startup:

```python
from key_registry import KeyRegistry

registry = KeyRegistry()
# Scans env vars matching SECRET_ENCRYPTION_KEY_V*
# registry.current_version -> 2
# registry.get_key(1) -> bytes (V1 key)
# registry.get_key(2) -> bytes (V2 key, used for new encryptions)
```

### Behavior

| Operation | Key Used |
|-----------|----------|
| Encrypt new secret | Highest version (`registry.current_version`) |
| Decrypt existing secret | Version stored alongside ciphertext |
| Re-encrypt during rotation | Decrypt with old version, encrypt with new |

Each stored secret record includes a `key_version` column indicating which
key was used to encrypt it.

## Rotation Procedure

### Step 1: Generate a New Key

```bash
# Generate a 256-bit key, base64-encoded
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Step 2: Add the New Key to Environment

Add the new key as the next version in the secret-broker environment
configuration:

```yaml
# infra/docker/docker-compose.yml (or .env file)
secret-broker:
  environment:
    SECRET_ENCRYPTION_KEY_V1: "existing-key-base64"
    SECRET_ENCRYPTION_KEY_V2: "new-key-base64"       # <-- add this
```

### Step 3: Restart the Secret-Broker

```bash
docker compose -f infra/docker/docker-compose.yml restart secret-broker
```

The KeyRegistry will detect both V1 and V2. New encryptions immediately use
V2. Existing secrets encrypted with V1 continue to decrypt normally.

### Step 4: Trigger Rotation

Call the rotation endpoint to re-encrypt all secrets in a workspace:

```bash
curl -X POST \
  http://localhost:8010/internal/v1/workspaces/{workspace_id}/secrets/rotate \
  -H "X-Internal-Auth: ${INTERNAL_AUTH_SECRET}"
```

**Response (202 Accepted):**

```json
{
  "workspace_id": "ws-abc123",
  "target_version": 2,
  "secrets_queued": 15,
  "status": "rotating"
}
```

The endpoint re-encrypts secrets in batches to avoid long-running transactions.

### Step 5: Verify Rotation Status

```bash
curl http://localhost:8010/internal/v1/workspaces/{workspace_id}/secrets/rotation-status \
  -H "X-Internal-Auth: ${INTERNAL_AUTH_SECRET}"
```

**Response:**

```json
{
  "workspace_id": "ws-abc123",
  "current_key_version": 2,
  "secrets_total": 15,
  "secrets_on_latest": 15,
  "secrets_on_older": 0,
  "rotation_complete": true
}
```

### Step 6: Remove the Old Key (Optional)

Once `secrets_on_older` is 0 for all workspaces, you may remove the old key
from the environment. This is optional but recommended to limit key exposure.

**Warning:** Do NOT remove the old key before all secrets are re-encrypted.
Doing so will make those secrets permanently unreadable.

## API Reference

### POST /internal/v1/workspaces/{workspace_id}/secrets/rotate

Triggers re-encryption of all workspace secrets to the latest key version.

| Parameter | Location | Required | Description |
|-----------|----------|----------|-------------|
| workspace_id | path | yes | Target workspace UUID |
| X-Internal-Auth | header | yes | Internal auth secret |

| Status | Meaning |
|--------|---------|
| 202 | Rotation started |
| 404 | Workspace not found |
| 409 | Rotation already in progress |

### GET /internal/v1/workspaces/{workspace_id}/secrets/rotation-status

Returns the current rotation state for a workspace.

| Parameter | Location | Required | Description |
|-----------|----------|----------|-------------|
| workspace_id | path | yes | Target workspace UUID |
| X-Internal-Auth | header | yes | Internal auth secret |

| Status | Meaning |
|--------|---------|
| 200 | Status returned |
| 404 | Workspace not found |

## Security Considerations

- Keys must be at least 256 bits (32 bytes) for AES-256.
- Store keys in a secrets manager (Vault, AWS Secrets Manager) in production.
  Environment variables are acceptable for development only.
- Audit logs record all rotation events (who triggered, when, result).
- The rotation endpoint is internal-only and requires `X-Internal-Auth`.
- Never log key material. The KeyRegistry redacts keys in debug output.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `KeyError: version 1 not found` | Old key removed before rotation complete | Re-add the old key, restart, re-check status |
| Rotation status shows `secrets_on_older > 0` | Rotation did not complete | Re-trigger rotation endpoint |
| 409 on rotation endpoint | Previous rotation still running | Wait for it to complete, check status endpoint |
| New secrets still on V1 | Service not restarted after adding V2 | Restart secret-broker |
