from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_manager
from database import get_pool

router = APIRouter(prefix="/pegawai", tags=["Pegawai"])


class PegawaiCreate(BaseModel):
    employee_code: str
    nama: str
    divisi: Optional[str] = None


class PegawaiResponse(BaseModel):
    id: int
    employee_code: str
    nama: str
    divisi: Optional[str]
    pelanggaran: int = 0


class PegawaiDetailResponse(PegawaiResponse):
    by_type: dict[str, int]


@router.get("/rekap", response_model=list[PegawaiResponse])
async def rekap_pegawai(_user: dict = Depends(get_current_user)):
    """List semua pegawai dengan jumlah pelanggaran masing-masing (urut terbanyak)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.employee_code, p.nama, p.divisi,
                   COUNT(v.id) AS pelanggaran
            FROM pegawai p
            LEFT JOIN violations v ON v.pegawai_id = p.id
            GROUP BY p.id, p.employee_code, p.nama, p.divisi
            ORDER BY pelanggaran DESC, p.nama ASC
        """)
        return [dict(r) for r in rows]


@router.get("/{pegawai_id}", response_model=PegawaiDetailResponse)
async def detail_pegawai(pegawai_id: int, _user: dict = Depends(get_current_user)):
    """Detail pegawai: identitas + breakdown pelanggaran per type."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, employee_code, nama, divisi FROM pegawai WHERE id = $1",
            pegawai_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")

        total = await conn.fetchval(
            "SELECT COUNT(*) FROM violations WHERE pegawai_id = $1", pegawai_id
        )
        type_rows = await conn.fetch(
            "SELECT violation_type, COUNT(*) AS c FROM violations "
            "WHERE pegawai_id = $1 GROUP BY violation_type",
            pegawai_id,
        )
        by_type = {r["violation_type"]: r["c"] for r in type_rows}

        return {**dict(row), "pelanggaran": total or 0, "by_type": by_type}


@router.post("", response_model=PegawaiResponse, status_code=201)
async def create_pegawai(
    body: PegawaiCreate,
    _manager: dict = Depends(require_manager),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO pegawai (employee_code, nama, divisi) "
                "VALUES ($1, $2, $3) RETURNING id, employee_code, nama, divisi",
                body.employee_code, body.nama, body.divisi,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {**dict(row), "pelanggaran": 0}
