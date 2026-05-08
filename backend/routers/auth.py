from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from auth import create_access_token, hash_password, verify_password
from database import get_pool

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    role: str = Field("user", pattern="^(user|manager)$")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


@router.post("/register", status_code=201)
async def register(body: RegisterRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE username = $1", body.username
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username sudah dipakai")
        await conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3)",
            body.username,
            hash_password(body.password),
            body.role,
        )
    return {"message": "Registrasi berhasil"}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash, role FROM users WHERE username = $1", body.username
        )
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
        )
    token = create_access_token(
        {"sub": str(row["id"]), "username": body.username, "role": row["role"]}
    )
    return TokenResponse(access_token=token, role=row["role"], username=body.username)
