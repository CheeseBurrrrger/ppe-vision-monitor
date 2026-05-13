"""
seed_pegawai_dummy.py
Seed dummy pegawai and randomly assign existing violations to them.
This stands in for the face-recognition feature until it lands.

Run inside the backend container:
    docker compose exec backend python /app/scripts/seed_pegawai_dummy.py

Or locally with DATABASE_URL set in env:
    python scripts/seed_pegawai_dummy.py
"""
import asyncio
import os
import random
import sys

import asyncpg

DUMMY_PEGAWAI = [
    ("EPS-0001", "Ahmad Fauzi",      "Spraying Room"),
    ("EPS-0002", "Budi Santoso",     "Assembly"),
    ("EPS-0003", "Citra Dewi",       "Quality Control"),
    ("EPS-0004", "Deni Kurniawan",   "Pipe Store"),
    ("EPS-0005", "Eka Putri",        "Spraying Room"),
    ("EPS-0006", "Fajar Hidayat",    "Console Area"),
    ("EPS-0007", "Gilang Ramadan",   "Assembly"),
    ("EPS-0008", "Hana Sari",        "Quality Control"),
    ("EPS-0009", "Irwan Setiawan",   "Pipe Store"),
    ("EPS-0010", "Joko Prasetyo",    "Console Area"),
]


async def main() -> None:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(dsn)
    try:
        # Insert pegawai if not exists
        inserted = 0
        for code, nama, divisi in DUMMY_PEGAWAI:
            row = await conn.fetchrow(
                "INSERT INTO pegawai (employee_code, nama, divisi) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (employee_code) DO NOTHING "
                "RETURNING id",
                code, nama, divisi,
            )
            if row:
                inserted += 1
        print(f"Pegawai inserted: {inserted} (skipped {len(DUMMY_PEGAWAI) - inserted} existing)")

        # Fetch all pegawai
        pegawai_rows = await conn.fetch("SELECT id FROM pegawai")
        pegawai_ids = [r["id"] for r in pegawai_rows]
        if not pegawai_ids:
            print("No pegawai found, aborting")
            return

        # Randomly assign existing violations to pegawai
        # Only target violations that don't already have a pegawai_id
        unassigned = await conn.fetch(
            "SELECT id FROM violations WHERE pegawai_id IS NULL"
        )
        if not unassigned:
            print("No unassigned violations to assign")
        else:
            random.seed(42)
            for v in unassigned:
                pid = random.choice(pegawai_ids)
                await conn.execute(
                    "UPDATE violations SET pegawai_id = $1 WHERE id = $2",
                    pid, v["id"],
                )
            print(f"Assigned {len(unassigned)} violations to random pegawai")

        # If there are no violations at all, create some dummy ones
        total_violations = await conn.fetchval("SELECT COUNT(*) FROM violations")
        if total_violations == 0:
            print("No violations exist — creating 30 dummy violations...")
            types = ["no_helmet", "no_vest", "no_safety_boot"]
            severities = {"no_helmet": "HIGH", "no_vest": "HIGH", "no_safety_boot": "MEDIUM"}
            for _ in range(30):
                vt = random.choice(types)
                pid = random.choice(pegawai_ids)
                await conn.execute(
                    """
                    INSERT INTO violations
                        (violation_type, confidence, severity, camera_id, pegawai_id, timestamp)
                    VALUES
                        ($1, $2, $3, $4, $5, NOW() - (random() * INTERVAL '7 days'))
                    """,
                    vt,
                    round(random.uniform(0.55, 0.95), 3),
                    severities[vt],
                    random.choice(["CAM_RUANG_PRODUKSI_1", "CAM_RUANG_PRODUKSI_2"]),
                    pid,
                )
            print("Done.")

        # Summary
        summary = await conn.fetch("""
            SELECT p.nama, COUNT(v.id) AS jumlah
            FROM pegawai p
            LEFT JOIN violations v ON v.pegawai_id = p.id
            GROUP BY p.id, p.nama
            ORDER BY jumlah DESC
        """)
        print("\nRekap pelanggaran per pegawai:")
        print("-" * 50)
        for r in summary:
            print(f"  {r['nama']:25s}  {r['jumlah']:>4} pelanggaran")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
