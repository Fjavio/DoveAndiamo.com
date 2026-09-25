from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.schemas import UserMessageRequest, LLMResponse
from models.entities import Partecipante
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

        #Se l'estrazione ha successo, salviamo l'Entity nel DB
        nuovo_partecipante = Partecipante(
            stanza_id=request.room_id,
            nome=request.user_id, # Temporaneo: mappiamo l'user_id come nome
            budget_max=response.profile.budget_max,
            orario_inizio=response.profile.orario_inizio,
            mezzo_trasporto=response.profile.mezzo_trasporto,
            zona_partenza=response.profile.zona_partenza,
            restrizioni_alimentari=response.profile.restrizioni_alimentari,
            preferenze_aggiuntive=response.profile.preferenze_aggiuntive
        )
        
        db.add(nuovo_partecipante)
        db.commit()
        db.refresh(nuovo_partecipante)
        
        return response
    except Exception as e:
        db.rollback()
        # Se Groq va in timeout o la chiave è errata, restituiamo un errore HTTP 500 controllato (RNF9)
        raise HTTPException(status_code=500, detail=str(e))