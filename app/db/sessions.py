from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .models import Base
from app.core.config import Config

def create_database():
    if Config.DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            Config.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    else:
        engine = create_engine(Config.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    return engine

engine = create_database()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
