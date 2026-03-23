"""Integration test fixtures — real PostgreSQL via Docker.

Uses the orchestrator's database (orchestrator_core schema).
Each test runs in a transaction that is rolled back afterward.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def db_engine():
    """Create engine connected to the orchestrator_core schema."""
    url = os.getenv(
        "ORCHESTRATOR_DB_URL",
        "postgresql://superuser:superpassword@localhost:5434/mona_os",
    )
    engine = create_engine(url)

    # Verify connection and schema
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO orchestrator_core"))
        conn.execute(text("SELECT 1"))

    return engine


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    # Set search path for this session
    session.execute(text("SET search_path TO orchestrator_core"))

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def session_factory(db_session):
    """Session factory that always returns the test session.

    This ensures the UoW uses the same transactional session.
    """
    class TestSessionFactory:
        def __call__(self):
            return db_session

    return TestSessionFactory()
