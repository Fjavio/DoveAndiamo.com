from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import random
import string
from datetime import timedelta
from db.database import get_db
from models.entities import Stanza
from models.schemas import RoomCreateRequest, RoomResponse

router = APIRouter(prefix="/rooms", tags=["Rooms"])

def genera_codice_invito(length=6) -> str:
    """Genera una stringa alfanumerica maiuscola casuale"""
    caratteri = string.ascii_uppercase + string.digits
    return ''.join(random.choices(caratteri, k=length))

@router.post("/", response_model=RoomResponse)
def create_room(request: RoomCreateRequest, db: Session = Depends(get_db)):
    """
    Crea una nuova stanza. Genera automaticamente il codice invito
    e imposta la scadenza a 24 ore dopo la data dell'uscita.
    """
    try:
        codice = genera_codice_invito()
        
        # Assicuriamoci che il codice sia univoco nel database
        while db.query(Stanza).filter(Stanza.codice_invito == codice).first():
            codice = genera_codice_invito()

        # RNF3: Impostiamo la scadenza a 24 ore dopo l'evento
        scadenza_calcolata = request.data + timedelta(days=1)
        
        nuova_stanza = Stanza(
            citta=request.citta,
            data=request.data,
            occasione=request.occasione,
            scadenza=scadenza_calcolata,
            codice_invito=codice
        )
        
        db.add(nuova_stanza)
        db.commit()
        db.refresh(nuova_stanza)
        
        return nuova_stanza

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/code/{codice}", response_model=RoomResponse)
def get_room_by_code(codice: str, db: Session = Depends(get_db)):
    """Verifica se una stanza esiste a partire dal codice invito"""
    stanza = db.query(Stanza).filter(Stanza.codice_invito == codice).first()
    if not stanza:
        raise HTTPException(status_code=404, detail="Stanza inesistente")
    return stanza