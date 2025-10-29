# alembic/env.py
from __future__ import annotations
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.db.base import Base
from app.core.config import settings

# ВАЖНО: явно импортируем все модели, чтобы они попали в Base.metadata
from app.models.product import Product
from app.models.robot import Robot
from app.models.inventory_history import InventoryHistory
from app.models.robot_history import RobotHistory
from app.models.warehouse import Warehouse

# Alembic Config
config = context.config

# Используем тот же URL, что и приложение
db_url = (
    getattr(settings, "DB_URL", None)
    or getattr(settings, "DATABASE_URL", None)
    or getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
)
if not db_url:
    raise RuntimeError("DB URL not found in settings (DB_URL / DATABASE_URL / SQLALCHEMY_DATABASE_URI).")
config.set_main_option("sqlalchemy.url", db_url)

# Логи из alembic.ini, если есть
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Мета-данные моделей
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
        include_object=None,   # можно сюда добавить фильтр, если нужно
    )
    with context.begin_transaction():
        context.run_migrations()

def _do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=None,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    import asyncio
    async def run():
        async with connectable.connect() as connection:
            await connection.run_sync(_do_run_migrations)
        await connectable.dispose()
    asyncio.run(run())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
