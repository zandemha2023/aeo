"""
Database migration utilities.

DEPRECATED: Use Alembic for migrations instead.

    # Run migrations
    alembic upgrade head

    # Create new migration
    alembic revision --autogenerate -m "description"

    # Rollback
    alembic downgrade -1

This file is kept for backwards compatibility with the check_connection utility.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import get_settings


async def check_connection() -> bool:
    """Check database connection."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("Database connection successful")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  alembic upgrade head     # Run migrations")
        print("  alembic downgrade -1     # Rollback one migration")
        print("  python -m db.migrations check  # Check connection")
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        asyncio.run(check_connection())
    else:
        print(f"Unknown command: {command}")
        print("Use 'alembic' for migration commands")
        sys.exit(1)
