from datetime import datetime
from typing import Optional
from database import get_pool


async def insert_violation(
    violation_type: str,
    confidence: float,
    timestamp: Optional[datetime] = None,
    frame_path: Optional[str] = None,
    camera_id: Optional[str] = "default",
) -> None:
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO violations (
                violation_type,
                confidence,
                timestamp,
                frame_path,
                camera_id
            )
            VALUES ($1, $2, COALESCE($3, NOW()), $4, $5)
            """,
            violation_type,
            confidence,
            timestamp,
            frame_path,
            camera_id,
        )
