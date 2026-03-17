from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# --- Violations ---
class ViolationCreate(BaseModel):
    violation_type: str = Field(..., examples=["no_helmet", "no_vest"])
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    frame_path: Optional[str] = None
    camera_id: Optional[str] = "default"

class ViolationResponse(BaseModel):
    id: int
    violation_type: str
    confidence: float
    timestamp: datetime
    frame_path: Optional[str]
    camera_id: Optional[str]
    created_at: datetime

class ViolationStats(BaseModel):
    total_violations: int
    by_type: dict[str, int]
    by_hour: list[dict]

# --- Health ---
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
