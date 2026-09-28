from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import random
import string
from datetime import timedelta
from db.database import get_db
from models.entities import Stanza
from models.schemas import RoomCreateRequest, RoomResponse
from models.entities import Partecipante
from core.solver import ItinerarySolver
from llm.extractor import generate_group_explanation

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
            codice_invito=codice,
            organizzatore=request.creatore
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

@router.get("/{room_id}/participants")
def get_room_participants(room_id: str, db: Session = Depends(get_db)):
    """Restituisce la lista di tutti i partecipanti salvati in una specifica stanza"""
    partecipanti = db.query(Partecipante).filter(Partecipante.stanza_id == room_id).all()
    return partecipanti

@router.get("/{room_id}/proposals")
async def generate_proposals(room_id: str, db: Session = Depends(get_db)):
    #organizzatore calcola l'itinerario finale
    stanza = db.query(Stanza).filter(Stanza.id == room_id).first()
    if not stanza:
        raise HTTPException(status_code=404, detail="Stanza non trovata")
        
    partecipanti = db.query(Partecipante).filter(Partecipante.stanza_id == room_id).all()
    if not partecipanti:
        raise HTTPException(status_code=400, detail="La stanza è vuota")
        
    solver = ItinerarySolver()
    risultato = solver.elabora_proposta(stanza, partecipanti)
    
    # Chiamata al LLM per la spiegazione finale
    spiegazione = await generate_group_explanation(
        risultato.get("vincoli_gruppo", {}), 
        risultato.get("locali_proposti", [])
    )
    risultato["messaggio_ia"] = spiegazione
    
    return risultato