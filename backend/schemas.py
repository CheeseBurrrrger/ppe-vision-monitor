from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field

ViolationType = Literal["no_helmet", "no_vest", "no_safety_boot"]
Severity = Literal["LOW", "MEDIUM", "HIGH"]

_DEFAULT_SEVERITY: dict[str, Severity] = {
    "no_helmet": "HIGH",
    "no_vest": "HIGH",
    "no_safety_boot": "MEDIUM",
}

def default_severity(violation_type: str) -> Severity:
    return _DEFAULT_SEVERITY.get(violation_type, "MEDIUM")

# Clean up frame_path and convert to relative URL for frontend.
def _frame_path_to_url(frame_path: Optional[str]) -> Optional[str]:
    if not frame_path:
        return None
    name = frame_path.replace("\\", "/").rsplit("/", 1)[-1]
    return f"/screenshots/{name}"

# --- Violations ---
class ViolationCreate(BaseModel):
    violation_type: ViolationType = Field(..., examples=["no_helmet"])
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Optional[Severity] = None
    timestamp: Optional[datetime] = None
    frame_path: Optional[str] = None
    camera_id: Optional[str] = "default"

class ViolationResponse(BaseModel):
    id: int
    violation_type: ViolationType
    confidence: float
    severity: Severity
    timestamp: datetime
    frame_path: Optional[str]
    camera_id: Optional[str]
    created_at: datetime

    @computed_field
    @property
    def screenshot_url(self) -> Optional[str]:
        return _frame_path_to_url(self.frame_path)

class ViolationStats(BaseModel):
    total_violations: int
    by_type: dict[str, int]
    by_hour: list[dict]

# --- Health ---
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
