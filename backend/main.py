from fastapi import FastAPI
from dotenv import load_dotenv
import os

# Carica le variabili d'ambiente prima di inizializzare qualsiasi altra cosa
load_dotenv()

from api.user_routes import router as user_router
from api.room_routes import router as room_router
from db.database import engine, Base
from models import entities

# Genera le tabelle fisiche su SQLite leggendo entities.py
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Jammo API",
    description="Backend per il sistema di organizzazione itinerari di gruppo",
    version="1.0.0"
)

app.include_router(user_router)
app.include_router(room_router)

#async: mentre il server aspetta che Groq risponda a un utente, non si blocca ma può rispondere alle richieste di altri utenti.
@app.get("/")
async def root():
    return {"message": "Jammo Backend è operativo!", "status": "online"}

@app.get("/health")
async def health_check():
    """
    Rotta di servizio per verificare lo stato del sistema e delle chiavi API.
    Utilissima per la piattaforma B2B per capire se il servizio è disponibile.
    """
    groq_key_present = bool(os.getenv("GROQ_API_KEY"))
    
    return {
        "status": "healthy",
        "services": {
            "groq_api_configured": groq_key_present
        }
    }