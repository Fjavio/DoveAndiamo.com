from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Creiamo un file SQLite locale nella cartella backend
SQLALCHEMY_DATABASE_URL = "sqlite:///./jammo.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dipendenza per iniettare la sessione del DB nelle rotte FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()