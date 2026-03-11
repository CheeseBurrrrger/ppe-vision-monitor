import asyncpg
from config import settings

pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
        )
    return pool

async def init_db() -> None:
    db = await get_pool()
    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id SERIAL PRIMARY KEY,
                violation_type VARCHAR(50) NOT NULL,
                confidence FLOAT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                frame_path VARCHAR(255),
                camera_id VARCHAR(50) DEFAULT 'default',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_violations_timestamp
            ON violations (timestamp);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_violations_type
            ON violations (violation_type);
        """)

async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None
