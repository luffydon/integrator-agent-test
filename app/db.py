from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

os.makedirs("data", exist_ok=True)
DB_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
