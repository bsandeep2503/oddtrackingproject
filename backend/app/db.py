import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nba_odds")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def reset_quarter_snapshots():
    from .models import QuarterSnapshot
    QuarterSnapshot.__table__.drop(bind=engine, checkfirst=True)
    QuarterSnapshot.__table__.create(bind=engine)
