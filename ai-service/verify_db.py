import asyncio
import sys

from app.db import get_engine, dispose_database_engine
from app.models.project_knowledge import Base

async def verify():
    engine = get_engine()
    print("Engine configured successfully.")
    try:
        async with engine.begin() as conn:
            print("Connecting to database...")
            # We specifically want to test pgvector extension is available
            await conn.run_sync(lambda sync_conn: sync_conn.execute(
                __import__('sqlalchemy').text('CREATE EXTENSION IF NOT EXISTS vector')
            ))
            print("pgvector extension verified.")
            
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            print("Schema initialized successfully.")
    except Exception as e:
        print(f"Database error: {type(e).__name__}")
        sys.exit(1)
    finally:
        await dispose_database_engine()

if __name__ == '__main__':
    asyncio.run(verify())
