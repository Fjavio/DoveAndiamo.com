from fastapi import APIRouter, HTTPException
from models.schemas import UserMessageRequest, LLMResponse
from llm.extractor import extract_user_profile

# Inizializza il router per questo modulo
router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/extract-profile", response_model=LLMResponse)
async def process_user_message(request: UserMessageRequest):
    """
    Riceve un messaggio in linguaggio naturale (RF02), lo passa all'LLM 
    ed estrae il profilo utente strutturato (RF03/RF04).
    """
    try:
        # Passiamo solo il testo del messaggio alla nostra funzione Groq
        response = await extract_user_profile(request.message)
        return response
    except Exception as e:
        # Se Groq va in timeout o la chiave è errata, restituiamo un errore HTTP 500 controllato (RNF9)
        raise HTTPException(status_code=500, detail=str(e))