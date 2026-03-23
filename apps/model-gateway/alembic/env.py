"""Alembic environment configuration for model-gateway."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable
db_url = os.getenv('MODEL_GW_DB_URL', 'postgresql://superuser:superpassword@localhost/mona_os')
config.set_main_option('sqlalchemy.url', db_url)

TARGET_SCHEMA = 'model_gateway_core'


def run_migrations_offline() -> None:
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        version_table_schema=TARGET_SCHEMA,
        include_schemas=[TARGET_SCHEMA],
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text(f'SET search_path TO {TARGET_SCHEMA}'))
        context.configure(
            connection=connection,
            target_metadata=None,
            version_table_schema=TARGET_SCHEMA,
            include_schemas=[TARGET_SCHEMA],
            transaction_per_migration=True,
        )
        context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
