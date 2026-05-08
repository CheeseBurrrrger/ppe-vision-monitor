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
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id SERIAL PRIMARY KEY,
                violation_type VARCHAR(50) NOT NULL,
                confidence FLOAT NOT NULL,
                severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                frame_path VARCHAR(255),
                camera_id VARCHAR(50) DEFAULT 'default',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                validated_by INTEGER REFERENCES users(id),
                validated_at TIMESTAMPTZ,
                notes TEXT
            );
        """)
        # Add new columns if upgrading from older schema
        for col_sql in [
            "ALTER TABLE violations ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "ALTER TABLE violations ADD COLUMN IF NOT EXISTS validated_by INTEGER REFERENCES users(id)",
            "ALTER TABLE violations ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ",
            "ALTER TABLE violations ADD COLUMN IF NOT EXISTS notes TEXT",
        ]:
            await conn.execute(col_sql)
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
