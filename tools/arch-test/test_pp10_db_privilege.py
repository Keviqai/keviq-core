"""PP10: Database privilege isolation — real PostgreSQL tests.

Tests privilege contracts after infra/docker/init-schemas.sql is applied.

What this proves:
  1. orchestrator_user CANNOT access artifact_core schema (cross-schema isolation)
  2. artifact_user CAN create and CRUD tables in artifact_core (owner privilege via
     bootstrap SQL's GRANT CREATE + DEFAULT PRIVILEGES)
  3. audit_user is APPEND-ONLY on granted tables (INSERT/SELECT yes, UPDATE/DELETE no)

What this does NOT prove:
  - audit_core DEFAULT PRIVILEGES correctness (fixture uses explicit grants,
    not bootstrap-created tables). Deferred to Phase B migration user path.

Requires: PostgreSQL running with init-schemas.sql already applied.
"""

import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv('PP10_DB_TEST', ''),
    reason='PP10 requires PostgreSQL — set PP10_DB_TEST=1 to enable',
)

DB_HOST = os.getenv('PGHOST', 'localhost')
DB_PORT = os.getenv('PGPORT', '5432')
DB_NAME = os.getenv('PGDATABASE', 'mona_os')

# Credentials match infra/docker/init-schemas.sql exactly
USERS = {
    'superuser':          {'password': 'superpassword'},
    'orchestrator_user':  {'password': 'orch_pass'},
    'artifact_user':      {'password': 'artifact_pass'},
    'audit_user':         {'password': 'audit_pass'},
}


def _connect(user: str):
    """Connect to PostgreSQL as a specific user."""
    import psycopg2
    creds = USERS[user]
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=user,
        password=creds['password'],
    )


@pytest.fixture(scope='module', autouse=True)
def setup_test_tables():
    """Create test tables for privilege verification.

    artifact_core table: Created BY artifact_user, proving that
    init-schemas.sql grants CREATE privilege correctly. No superuser
    grants are added — this proves the bootstrap SQL works.

    audit_core table: Created by superuser with explicit grants matching
    init-schemas.sql policy. This does NOT prove DEFAULT PRIVILEGES work
    for audit tables — it only proves that the append-only privilege
    model (INSERT+SELECT, no UPDATE/DELETE) is enforceable. A full
    bootstrap proof for audit would require a dedicated migration user
    path, which is deferred to Phase B.
    """
    # artifact_user creates its own table in artifact_core
    # This proves init-schemas.sql's GRANT CREATE actually works
    conn = _connect('artifact_user')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS artifact_core.pp10_test_artifact (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    cur.close()
    conn.close()

    # audit_core: superuser creates table + explicit grants
    # This simulates the production path where a migration user (not
    # audit_user) creates tables, then audit_user gets limited access.
    # NOTE: This proves append-only enforcement, NOT bootstrap correctness.
    conn = _connect('superuser')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_core.pp10_test_audit_log (
            id SERIAL PRIMARY KEY,
            action TEXT NOT NULL,
            detail TEXT
        )
    """)
    cur.execute("GRANT INSERT, SELECT ON audit_core.pp10_test_audit_log TO audit_user")
    cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit_core TO audit_user")
    cur.close()
    conn.close()

    yield

    # Cleanup
    conn = _connect('superuser')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS artifact_core.pp10_test_artifact")
    cur.execute("DROP TABLE IF EXISTS audit_core.pp10_test_audit_log")
    cur.close()
    conn.close()


# ── PP10-A: Cross-schema isolation ──────────────────────────


class TestPP10CrossSchemaIsolation:
    """orchestrator_user must NOT be able to touch artifact_core.

    This proves init-schemas.sql does NOT grant orchestrator_user any
    privilege on artifact_core — the schemas are isolated.
    """

    def test_orchestrator_has_no_usage_on_artifact_core(self):
        """Verify via pg metadata that orchestrator_user lacks USAGE."""
        conn = _connect('superuser')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT has_schema_privilege('orchestrator_user', 'artifact_core', 'USAGE')"
        )
        has_usage = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert has_usage is False, (
            "PP10 VIOLATION: orchestrator_user has USAGE on artifact_core"
        )

    def test_orchestrator_cannot_insert_into_artifact_core(self):
        """orchestrator_user is denied INSERT — real SQL execution test."""
        import psycopg2
        conn = _connect('orchestrator_user')
        conn.autocommit = True
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO artifact_core.pp10_test_artifact (name) VALUES ('should_fail')"
            )
        cur.close()
        conn.close()

    def test_orchestrator_cannot_select_from_artifact_core(self):
        """orchestrator_user is denied SELECT — real SQL execution test."""
        import psycopg2
        conn = _connect('orchestrator_user')
        conn.autocommit = True
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM artifact_core.pp10_test_artifact")
        cur.close()
        conn.close()

    def test_orchestrator_has_no_create_on_artifact_core(self):
        """orchestrator_user cannot CREATE tables in artifact_core."""
        conn = _connect('superuser')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT has_schema_privilege('orchestrator_user', 'artifact_core', 'CREATE')"
        )
        has_create = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert has_create is False, (
            "PP10 VIOLATION: orchestrator_user has CREATE on artifact_core"
        )


# ── PP10-B: Service user owns its schema ─────────────────────


class TestPP10ServiceOwnerPrivilege:
    """artifact_user must have full CRUD on tables it creates in artifact_core.

    Table was created BY artifact_user in the fixture, proving that
    init-schemas.sql's GRANT CREATE actually works.
    """

    def test_artifact_user_can_insert(self):
        conn = _connect('artifact_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO artifact_core.pp10_test_artifact (name) VALUES ('test_insert')"
        )
        cur.close()
        conn.close()

    def test_artifact_user_can_select(self):
        conn = _connect('artifact_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM artifact_core.pp10_test_artifact")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert count >= 0

    def test_artifact_user_can_update(self):
        conn = _connect('artifact_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "UPDATE artifact_core.pp10_test_artifact SET name = 'updated' WHERE name = 'test_insert'"
        )
        cur.close()
        conn.close()

    def test_artifact_user_can_delete(self):
        conn = _connect('artifact_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DELETE FROM artifact_core.pp10_test_artifact WHERE name = 'updated'")
        cur.close()
        conn.close()

    def test_artifact_user_has_create_on_own_schema(self):
        """artifact_user must have CREATE privilege on artifact_core."""
        conn = _connect('superuser')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT has_schema_privilege('artifact_user', 'artifact_core', 'CREATE')"
        )
        has_create = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert has_create is True, (
            "PP10 VIOLATION: artifact_user lacks CREATE on artifact_core"
        )


# ── PP10-C: Audit user is append-only ────────────────────────


class TestPP10AuditAppendOnly:
    """audit_user can INSERT and SELECT, but NOT UPDATE or DELETE.

    This proves the append-only contract from init-schemas.sql.
    """

    def test_audit_user_has_no_create_privilege(self):
        """audit_user must NOT have CREATE — cannot make new tables."""
        conn = _connect('superuser')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT has_schema_privilege('audit_user', 'audit_core', 'CREATE')"
        )
        has_create = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert has_create is False, (
            "PP10 VIOLATION: audit_user has CREATE on audit_core — "
            "should be append-only, no schema modification allowed"
        )

    def test_audit_user_can_insert(self):
        conn = _connect('audit_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_core.pp10_test_audit_log (action, detail) "
            "VALUES ('test_action', 'should_succeed')"
        )
        cur.close()
        conn.close()

    def test_audit_user_can_select(self):
        conn = _connect('audit_user')
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_core.pp10_test_audit_log")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert count >= 1

    def test_audit_user_cannot_update(self):
        """audit_user must be denied UPDATE — append-only enforcement."""
        import psycopg2
        conn = _connect('audit_user')
        conn.autocommit = True
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "UPDATE audit_core.pp10_test_audit_log SET detail = 'tampered' "
                "WHERE action = 'test_action'"
            )
        cur.close()
        conn.close()

    def test_audit_user_cannot_delete(self):
        """audit_user must be denied DELETE — append-only enforcement."""
        import psycopg2
        conn = _connect('audit_user')
        conn.autocommit = True
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "DELETE FROM audit_core.pp10_test_audit_log WHERE action = 'test_action'"
            )
        cur.close()
        conn.close()
