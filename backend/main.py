import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import settings
from database import close_pool, init_db
from routers import health, violations

logger = logging.getLogger(__name__)

def _mount_screenshots(app: FastAPI) -> None:
    default = Path(__file__).parent.parent / "screenshots"
    path = Path(os.getenv("SCREENSHOTS_DIR", str(default)))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "SCREENSHOTS_DIR %s tidak dapat dibuat (%s); /screenshots non-aktif.",
            path, exc,
        )
        return
    app.mount("/screenshots", StaticFiles(directory=str(path)), name="screenshots")
    logger.info("Static /screenshots → %s", path)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_pool()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(violations.router, tags=["Violations"])
_mount_screenshots(app)
