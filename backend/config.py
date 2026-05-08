import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "PPE Vision Monitor API"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = os.getenv("DATABASE_URL")

    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # Internal service key for CV core → backend communication
    CV_SERVICE_KEY: str = os.getenv("CV_SERVICE_KEY", "")

settings = Settings()
