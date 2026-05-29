import asyncio
import urllib.parse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.services.api.user_app.config import settings


async def inspect():
    user = urllib.parse.quote_plus(settings.DB_USER)
    password = urllib.parse.quote_plus(settings.DB_PASSWORD)
    db_url = f"postgresql+psycopg2://{user}:{password}@{settings.DB_MASTER_HOST}:{settings.DB_MASTER_PORT}/{settings.DB_NAME}"

    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = result.scalars().all()
        print("Existing tables:", tables)

        # Check alembic version
        try:
            v_result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            version = v_result.scalar()
            print("Alembic version:", version)
        except Exception as e:
            print("Alembic version table missing or error:", e)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(inspect())
