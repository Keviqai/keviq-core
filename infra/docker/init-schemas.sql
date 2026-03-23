-- Keviq Core: Database schema initialization
-- Creates schemas per service ownership (doc 13 mục 13.16)
-- Each service owns a non-overlapping schema (S1)
-- Idempotent: safe to re-run on existing databases.

-- ── Schemas ──────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS orchestrator_core;
CREATE SCHEMA IF NOT EXISTS agent_runtime;
CREATE SCHEMA IF NOT EXISTS artifact_core;
CREATE SCHEMA IF NOT EXISTS execution_core;
CREATE SCHEMA IF NOT EXISTS identity_core;
CREATE SCHEMA IF NOT EXISTS workspace_core;
CREATE SCHEMA IF NOT EXISTS policy_core;
CREATE SCHEMA IF NOT EXISTS secret_core;
CREATE SCHEMA IF NOT EXISTS model_gateway_core;
CREATE SCHEMA IF NOT EXISTS audit_core;
CREATE SCHEMA IF NOT EXISTS event_core;
CREATE SCHEMA IF NOT EXISTS notification_core;
CREATE SCHEMA IF NOT EXISTS telemetry_core;

-- ── Users with schema-scoped permissions (PP1, PP10) ─────────
-- Uses DO blocks to make CREATE USER idempotent (safe on re-run).

-- orchestrator_user: owns orchestrator_core only
DO $$ BEGIN CREATE USER orchestrator_user WITH PASSWORD 'orch_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA orchestrator_core TO orchestrator_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA orchestrator_core TO orchestrator_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA orchestrator_core GRANT ALL ON TABLES TO orchestrator_user;

-- artifact_user: owns artifact_core only
DO $$ BEGIN CREATE USER artifact_user WITH PASSWORD 'artifact_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA artifact_core TO artifact_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA artifact_core TO artifact_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA artifact_core GRANT ALL ON TABLES TO artifact_user;

-- agent_runtime_user: owns agent_runtime only
DO $$ BEGIN CREATE USER agent_runtime_user WITH PASSWORD 'agent_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA agent_runtime TO agent_runtime_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agent_runtime TO agent_runtime_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent_runtime GRANT ALL ON TABLES TO agent_runtime_user;

-- auth_user: owns identity_core only
DO $$ BEGIN CREATE USER auth_user WITH PASSWORD 'auth_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA identity_core TO auth_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA identity_core TO auth_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA identity_core GRANT ALL ON TABLES TO auth_user;

-- policy_user: owns policy_core only
DO $$ BEGIN CREATE USER policy_user WITH PASSWORD 'policy_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA policy_core TO policy_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA policy_core TO policy_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA policy_core GRANT ALL ON TABLES TO policy_user;

-- audit_user: owns audit_core — APPEND-ONLY (no UPDATE, no DELETE on data)
-- CREATE on schema is needed for Alembic migrations (DDL); data access is still append-only.
DO $$ BEGIN CREATE USER audit_user WITH PASSWORD 'audit_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA audit_core TO audit_user;
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA audit_core TO audit_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit_core GRANT INSERT, SELECT ON TABLES TO audit_user;
-- NOTE: No UPDATE, No DELETE for audit_user (append-only enforcement on data)

-- execution_user: owns execution_core only
DO $$ BEGIN CREATE USER execution_user WITH PASSWORD 'exec_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA execution_core TO execution_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA execution_core TO execution_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA execution_core GRANT ALL ON TABLES TO execution_user;

-- workspace_user: owns workspace_core only
DO $$ BEGIN CREATE USER workspace_user WITH PASSWORD 'workspace_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA workspace_core TO workspace_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA workspace_core TO workspace_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA workspace_core GRANT ALL ON TABLES TO workspace_user;

-- secret_user: owns secret_core only
DO $$ BEGIN CREATE USER secret_user WITH PASSWORD 'secret_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA secret_core TO secret_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA secret_core TO secret_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA secret_core GRANT ALL ON TABLES TO secret_user;

-- model_gw_user: owns model_gateway_core only
DO $$ BEGIN CREATE USER model_gw_user WITH PASSWORD 'model_gw_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA model_gateway_core TO model_gw_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA model_gateway_core TO model_gw_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA model_gateway_core GRANT ALL ON TABLES TO model_gw_user;

-- event_store_user: owns event_core — APPEND-ONLY on events table
-- outbox table needs full CRUD (publish + mark as published), but events table is append-only
DO $$ BEGIN CREATE USER event_store_user WITH PASSWORD 'event_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA event_core TO event_store_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA event_core TO event_store_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA event_core GRANT ALL ON TABLES TO event_store_user;
-- NOTE: Application layer enforces append-only on events table.
-- DB-level restriction (INSERT+SELECT only) deferred until outbox relay is split
-- into a separate service, since event_store_user currently needs UPDATE on outbox
-- (to mark published_at). See Phase C for service separation.

-- notification_user: owns notification_core only
DO $$ BEGIN CREATE USER notification_user WITH PASSWORD 'notif_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA notification_core TO notification_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA notification_core TO notification_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA notification_core GRANT ALL ON TABLES TO notification_user;

-- telemetry_user: owns telemetry_core only
DO $$ BEGIN CREATE USER telemetry_user WITH PASSWORD 'telemetry_pass'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT USAGE, CREATE ON SCHEMA telemetry_core TO telemetry_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA telemetry_core TO telemetry_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA telemetry_core GRANT ALL ON TABLES TO telemetry_user;
