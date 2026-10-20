import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'todo.db'}"
)

# Support Neon PostgreSQL with psycopg 3
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "change-this-development-secret-before-deploying"
)

SESSION_HTTPS_ONLY = os.getenv(
    "SESSION_HTTPS_ONLY", "false"
).lower() == "true"