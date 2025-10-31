from __future__ import annotations
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from app.core.config import settings
from app.db.base import Base
import app.models  
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
db_url = (
    getattr(settings, "DB_URL", None)
    or getattr(settings, "DATABASE_URL", None)
    or getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
)
if not db_url:
    raise RuntimeError("DB URL not found in settings (DB_URL / DATABASE_URL / SQLALCHEMY_DATABASE_URI).")
config.set_main_option("sqlalchemy.url", settings.DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Эта функция запускается на sync-connection внутри async run_sync()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    from sqlalchemy.ext.asyncio import async_engine_from_config
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    import asyncio
    async def run():
        async with connectable.connect() as connection:
            # ВАЖНО: передаём sync-функцию в run_sync
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()