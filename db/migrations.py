"""
Database migration utilities.

For initial setup, run: python -m db.migrations create_tables
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import get_settings
from db.models import Base


async def create_tables() -> None:
    """Create all database tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Tables created successfully")


async def drop_tables() -> None:
    """Drop all database tables (use with caution!)."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("Tables dropped")


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
        print("Usage: python -m db.migrations [create_tables|drop_tables|check]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create_tables":
        asyncio.run(create_tables())
    elif command == "drop_tables":
        asyncio.run(drop_tables())
    elif command == "check":
        asyncio.run(check_connection())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
