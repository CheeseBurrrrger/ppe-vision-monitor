import csv
import io
from datetime import date, datetime, time
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from database import get_pool
from schemas import (
    ViolationCreate,
    ViolationResponse,
    ViolationStats,
    ViolationType,
    default_severity,
)

CSV_COLUMNS = [
    "id", "violation_type", "confidence", "severity", "timestamp",
    "camera_id", "frame_path", "created_at",
]

router = APIRouter()

@router.get("/violations", response_model=list[ViolationResponse])
async def get_violations(
    violation_type: Optional[ViolationType] = Query(
        None, description="Filter by type"
    ),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List violation events with optional filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM violations WHERE 1=1"
        params: list = []
        idx = 1

        if violation_type:
            query += f" AND violation_type = ${idx}"
            params.append(violation_type)
            idx += 1

        if date_from:
            query += f" AND timestamp >= ${idx}"
            params.append(datetime.combine(date_from, time.min))
            idx += 1

        if date_to:
            query += f" AND timestamp <= ${idx}"
            params.append(datetime.combine(date_to, time.max))
            idx += 1

        query += f" ORDER BY timestamp DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

@router.post("/violations", response_model=ViolationResponse, status_code=201)
async def create_violation(violation: ViolationCreate):
    """Record a new violation event."""
    severity = violation.severity or default_severity(violation.violation_type)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO violations (violation_type, confidence, severity, timestamp, frame_path, camera_id)
            VALUES ($1, $2, $3, COALESCE($4, NOW()), $5, $6)
            RETURNING *
            """,
            violation.violation_type,
            violation.confidence,
            severity,
            violation.timestamp,
            violation.frame_path,
            violation.camera_id,
        )
        if row is None:
            raise HTTPException(status_code=500, detail="Failed to create violation")
        return dict(row)

@router.get("/stats", response_model=ViolationStats)
async def get_stats():
    """Get aggregated violation statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM violations")

        type_rows = await conn.fetch(
            "SELECT violation_type, COUNT(*) as count "
            "FROM violations GROUP BY violation_type"
        )
        by_type = {row["violation_type"]: row["count"] for row in type_rows}

        hour_rows = await conn.fetch(
            "SELECT EXTRACT(HOUR FROM timestamp)::int as hour, COUNT(*) as count "
            "FROM violations GROUP BY hour ORDER BY hour"
        )
        by_hour = [{"hour": row["hour"], "count": row["count"]} for row in hour_rows]

        return ViolationStats(
            total_violations=total or 0,
            by_type=by_type,
            by_hour=by_hour,
        )

@router.get("/export-csv")
async def export_violations_csv(
    violation_type: Optional[ViolationType] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Download semua pelanggaran (yang lolos filter) sebagai CSV."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM violations WHERE 1=1"
        params: list = []
        idx = 1
        if violation_type:
            query += f" AND violation_type = ${idx}"
            params.append(violation_type)
            idx += 1
        if date_from:
            query += f" AND timestamp >= ${idx}"
            params.append(datetime.combine(date_from, time.min))
            idx += 1
        if date_to:
            query += f" AND timestamp <= ${idx}"
            params.append(datetime.combine(date_to, time.max))
            idx += 1
        query += " ORDER BY timestamp DESC"
        rows = await conn.fetch(query, *params)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))
    buf.seek(0)

    filename = f"violations_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
