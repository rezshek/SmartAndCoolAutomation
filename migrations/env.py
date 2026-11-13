from alembic import context

from smartandcool.catalog import models  # noqa: F401 -- register domain metadata
from smartandcool.config import Settings
from smartandcool.dashboard import models as dashboard_models  # noqa: F401
from smartandcool.db import Base, create_db_engine

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_db_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
