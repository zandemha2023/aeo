"""FastAPI dependencies for AEO Orchestrator."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import get_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session as a dependency."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
