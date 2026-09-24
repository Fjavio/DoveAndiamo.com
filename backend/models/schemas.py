"""
Pydantic ci serve a due scopi:
1. Controlla che le richieste inviate da Streamlit (o dalla piattaforma B2B) abbiano tutti i campi obbligatori.
2. Obbligheremo Groq a rispondere esattamente con questa struttura JSON, impedendogli di inventare chiavi a caso o di scrivere testo libero quando ci serve un dato strutturato.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================
# Richieste dal Frontend
# ==========================================

class UserMessageRequest(BaseModel):
    """Payload inviato dal client quando un utente scrive un messaggio (RF02)"""
    user_id: str = Field(..., description="ID univoco dell'utente")
    room_id: str = Field(..., description="ID della stanza virtuale")
    message: str = Field(..., description="Il messaggio in linguaggio naturale")

# ==========================================
# MODELLI DI OUTPUT (Estratti dall'LLM)
# ==========================================

class ExtractedProfile(BaseModel):
    """Struttura dati che pretendiamo da Groq dopo l'analisi del testo (RF03)"""
    budget_max: Optional[float] = Field(
        None, description="Budget massimo in euro. Null se non specificato."
    )
    orario_inizio: Optional[str] = Field(
        None, description="Orario di disponibilità nel formato HH:MM (es. '21:00')."
    )
    restrizioni_alimentari: List[str] = Field(
        default_factory=list, description="Lista di restrizioni (es. ['vegetariano', 'celiaco'])."
    )
    zona_partenza: Optional[str] = Field(
        None, description="Quartiere o zona geografica di partenza."
    )
    mezzo_trasporto: Optional[str] = Field(
        None, description="Mezzo utilizzato (es. 'auto', 'mezzi pubblici', 'piedi')."
    )
    preferenze_aggiuntive: List[str] = Field(
        default_factory=list, description="Desideri extra legati all'atmosfera, tipo di locale o servizi (es. 'musica dal vivo', 'romantico', 'tranquillo')."
    )
    
    # Questo campo implementa il requisito RF04 (Richiesta Chiarimento)
    richiesta_chiarimento: Optional[str] = Field(
        None, description="Testo della domanda da fare all'utente SE E SOLO SE la zona_partenza è ambigua."
    )

class LLMResponse(BaseModel):
    """Risposta standardizzata restituita al client dopo l'estrazione"""
    status: str = Field(..., description="'success' o 'clarification_needed'")
    profile: Optional[ExtractedProfile] = None
    message_to_user: Optional[str] = None