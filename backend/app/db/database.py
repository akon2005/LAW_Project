import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Database URL
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "metadata.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True) # Our stable hash ID
    case_name = Column(String, index=True)
    citation = Column(String, index=True)
    year = Column(Integer, index=True)
    court = Column(String, index=True)
    legal_domain = Column(String, index=True)
    section = Column(String)
    source = Column(String)
    record_type = Column(String, index=True)
    valid_from = Column(Integer)
    valid_until = Column(Integer, nullable=True)
    contains_outcome_language = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
