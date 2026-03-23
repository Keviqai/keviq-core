"""Create task_templates and agent_templates tables with system seed data.

S2: Template Models — foundation for Q1 delegation clarity.
System templates seeded via INSERT ON CONFLICT DO NOTHING.

Revision ID: a007
Revises: a006
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a007'
down_revision = 'a006'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    # ── Task Templates ────────────────────────────────────────
    op.create_table(
        'task_templates',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('prefilled_fields', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('expected_output_type', sa.Text(), nullable=True),
        sa.Column('scope', sa.Text(), nullable=False,
                  server_default='system'),
        sa.Column('workspace_id', UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "scope IN ('system', 'workspace')",
            name='ck_tt_scope',
        ),
        sa.CheckConstraint(
            "category IN ('research', 'analysis', 'operation', 'custom')",
            name='ck_tt_category',
        ),
        sa.CheckConstraint(
            "(scope = 'system' AND workspace_id IS NULL) OR "
            "(scope = 'workspace' AND workspace_id IS NOT NULL)",
            name='ck_tt_ws',
        ),
        schema=SCHEMA,
    )

    # ── Agent Templates ───────────────────────────────────────
    op.create_table(
        'agent_templates',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('best_for', sa.Text(), nullable=True),
        sa.Column('not_for', sa.Text(), nullable=True),
        sa.Column('capabilities_manifest', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('default_output_types', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('default_risk_profile', sa.Text(), nullable=False,
                  server_default='medium'),
        sa.Column('scope', sa.Text(), nullable=False,
                  server_default='system'),
        sa.Column('workspace_id', UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "scope IN ('system', 'workspace')",
            name='ck_at_scope',
        ),
        sa.CheckConstraint(
            "default_risk_profile IN ('low', 'medium', 'high')",
            name='ck_at_risk',
        ),
        sa.CheckConstraint(
            "(scope = 'system' AND workspace_id IS NULL) OR "
            "(scope = 'workspace' AND workspace_id IS NOT NULL)",
            name='ck_at_ws',
        ),
        schema=SCHEMA,
    )

    # ── FK from tasks to templates ────────────────────────────
    op.create_foreign_key(
        'fk_tasks_template_id', 'tasks', 'task_templates',
        ['template_id'], ['id'],
        source_schema=SCHEMA, referent_schema=SCHEMA,
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_tasks_agent_template_id', 'tasks', 'agent_templates',
        ['agent_template_id'], ['id'],
        source_schema=SCHEMA, referent_schema=SCHEMA,
        ondelete='SET NULL',
    )

    # ── Seed system templates ─────────────────────────────────
    _seed_task_templates()
    _seed_agent_templates()


def _seed_task_templates() -> None:
    op.execute(f"""
    INSERT INTO {SCHEMA}.task_templates (id, name, description, category,
        prefilled_fields, expected_output_type, scope)
    VALUES
    ('00000000-0000-4000-a000-000000000001',
     'Research Brief',
     'Research a topic and produce a structured brief with sources.',
     'research',
     '{{"goal": "Research and synthesize information on a given topic",
       "desired_output": "Structured brief with key findings and sources"}}'::jsonb,
     'report', 'system'),
    ('00000000-0000-4000-a000-000000000002',
     'Ops Case Prep',
     'Prepare a case file or operations memo with evidence and recommendations.',
     'operation',
     '{{"goal": "Prepare case documentation with evidence and next steps",
       "constraints": "Follow workspace policy for sensitive data handling",
       "desired_output": "Case memo with evidence summary and recommendations"}}'::jsonb,
     'memo', 'system'),
    ('00000000-0000-4000-a000-000000000003',
     'Data Analysis',
     'Analyze data and extract actionable insights with visualizations.',
     'analysis',
     '{{"goal": "Analyze dataset and extract actionable insights",
       "desired_output": "Analysis report with key metrics and recommendations"}}'::jsonb,
     'analysis', 'system')
    ON CONFLICT DO NOTHING
    """)


def _seed_agent_templates() -> None:
    op.execute(f"""
    INSERT INTO {SCHEMA}.agent_templates (id, name, description, best_for, not_for,
        capabilities_manifest, default_output_types, default_risk_profile, scope)
    VALUES
    ('00000000-0000-4000-b000-000000000001',
     'Research Analyst',
     'Gathers information from multiple sources, synthesizes findings, and produces structured reports.',
     'Literature review, data gathering, topic synthesis, competitive analysis',
     'Code execution, system administration, real-time data processing',
     '["web_search", "document_analysis", "summarization"]'::jsonb,
     '["report", "brief", "memo"]'::jsonb,
     'low', 'system'),
    ('00000000-0000-4000-b000-000000000002',
     'Ops Assistant',
     'Prepares case files, checklists, and operational documents following structured processes.',
     'Document drafting, checklist generation, evidence compilation, form filling',
     'Creative writing, code generation, data visualization',
     '["document_drafting", "checklist_generation", "data_extraction"]'::jsonb,
     '["memo", "checklist", "report"]'::jsonb,
     'medium', 'system'),
    ('00000000-0000-4000-b000-000000000003',
     'General Agent',
     'Versatile agent for mixed tasks including research, analysis, and light coding.',
     'Mixed tasks, general research, basic analysis, simple code generation',
     'Highly specialized domain tasks, production deployments, sensitive data handling',
     '["web_search", "document_analysis", "code_generation", "summarization"]'::jsonb,
     '["report", "code", "analysis"]'::jsonb,
     'medium', 'system')
    ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_constraint('fk_tasks_agent_template_id', 'tasks', schema=SCHEMA)
    op.drop_constraint('fk_tasks_template_id', 'tasks', schema=SCHEMA)
    op.drop_table('agent_templates', schema=SCHEMA)
    op.drop_table('task_templates', schema=SCHEMA)
