import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#crea cartella data per contenere il database SQLite
os.makedirs("./data", exist_ok=True)

# Spostiamo il file SQLite dentro la cartella "data" montata come volume in Docker
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/jammo.db"

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