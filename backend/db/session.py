import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(os.path.dirname(BASE_DIR), ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=True)

raw_database_url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
environment = os.getenv("ENVIRONMENT", "development").lower()

if raw_database_url:
    # Render and Neon compatibility: replace legacy postgres:// with postgresql://
    if raw_database_url.startswith("postgres://"):
        database_url = raw_database_url.replace("postgres://", "postgresql://", 1)
    else:
        database_url = raw_database_url
elif environment == "production":
    raise RuntimeError(
        "DATABASE_URL is strictly mandatory in production environment. "
        "Please configure DATABASE_URL in Render dashboard."
    )
else:
    # Development fallback
    db_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(db_dir, exist_ok=True)
    sqlite_path = os.path.join(db_dir, "local_dev.db")
    database_url = f"sqlite:///{sqlite_path}"

connect_args = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
