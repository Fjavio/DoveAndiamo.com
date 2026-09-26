from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.schemas import UserMessageRequest, LLMResponse
from models.entities import Partecipante, Stanza
from llm.extractor import extract_user_profile
from db.database import get_db

# Inizializza il router per questo modulo
router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

#Riceve un messaggio in linguaggio naturale, lo passa all'LLM  ed estrae il profilo utente strutturato.
@router.post("/extract-profile", response_model=LLMResponse)
async def process_user_message(request: UserMessageRequest, db: Session = Depends(get_db)):
    
    try:
        #Delega al BProviderLLM l'estrazione passandogli testo del messaggio
        response = await extract_user_profile(request.message)

        #Se l'LLM chiede chiarimenti, ci fermiamo e avvisiamo il frontend
        if response.status == "clarification_needed":
            return response

        # Aggiorniamo l'Entity nel DB
        partecipante = db.query(Partecipante).filter_by(
            stanza_id=request.room_id, nome=request.user_id
        ).first()
        
        if partecipante:
            partecipante.budget_max = response.profile.budget_max
            partecipante.disponibile_da = response.profile.disponibile_da
            partecipante.disponibile_a = response.profile.disponibile_a
            partecipante.zona_partenza = response.profile.zona_partenza
            partecipante.mezzo_trasporto = response.profile.mezzo_trasporto
            partecipante.mezzi_esclusi = response.profile.mezzi_esclusi
            partecipante.importanza_distanza = response.profile.importanza_distanza
            partecipante.restrizioni_alimentari = response.profile.restrizioni_alimentari
            partecipante.preferenze_aggiuntive = response.profile.preferenze_aggiuntive
            db.commit()
        
        return response
    except Exception as e:
        db.rollback()
        # Se Groq va in timeout o la chiave è errata, restituiamo un errore HTTP 500 controllato (RNF9)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{nickname}/rooms")
def get_user_rooms(nickname: str, db: Session = Depends(get_db)):
    """Recupera tutte le stanze a cui un utente si è unito"""
    partecipazioni = db.query(Partecipante).filter(Partecipante.nome == nickname).all()
    risultato = []
    for p in partecipazioni:
        if p.stanza:
            risultato.append({
                "id": p.stanza.id,
                "codice": p.stanza.codice_invito,
                "nome": p.stanza.occasione or f"Uscita a {p.stanza.citta}",
                "organizzatore": p.stanza.organizzatore
            })
    return risultato

@router.post("/{nickname}/join/{codice}")
def join_room(nickname: str, codice: str, db: Session = Depends(get_db)):
    """Collega un utente a una stanza nel database prima che inserisca le preferenze"""
    stanza = db.query(Stanza).filter(Stanza.codice_invito == codice).first()
    if not stanza:
        raise HTTPException(status_code=404, detail="Stanza inesistente")
        
    esistente = db.query(Partecipante).filter_by(stanza_id=stanza.id, nome=nickname).first()
    
    # Se non è ancora nella stanza, creiamo un record base
    if not esistente:
        nuovo = Partecipante(stanza_id=stanza.id, nome=nickname)
        db.add(nuovo)
        db.commit()
        
    return {
        "id": stanza.id,
        "codice": stanza.codice_invito,
        "nome": stanza.occasione or f"Uscita a {stanza.citta}",
        "organizzatore": stanza.organizzatore
    }