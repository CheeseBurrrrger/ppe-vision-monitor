import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "PPE Vision Monitor API"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = os.getenv("DATABASE_URL")

    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS").split(",")
    ]

settings = Settings()
