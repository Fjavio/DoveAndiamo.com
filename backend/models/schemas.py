from pydantic import BaseModel, Field #Controlla che le richieste inviate da Streamlit/piattaforma B2B abbiano tutti i campi obbligatori: obbligheremo Groq a rispondere esattamente con questa struttura JSON
from typing import List, Optional
from datetime import datetime

# ==========================================
# Richieste dal Frontend
# ==========================================

class UserMessageRequest(BaseModel):
    """Payload inviato dal client quando un utente scrive un messaggio (RF02)"""
    user_id: str = Field(..., description="ID univoco dell'utente")
    room_id: str = Field(..., description="ID della stanza virtuale")
    message: str = Field(..., description="Il messaggio in linguaggio naturale")

class RoomCreateRequest(BaseModel):
    """Payload inviato dall'organizzatore per creare una nuova stanza"""
    citta: str = Field(..., description="Città dell'uscita")
    data: datetime = Field(..., description="Data e ora indicativa dell'uscita")
    occasione: Optional[str] = Field(None, description="Occasione dell'uscita")
    creatore: str = Field(..., description="Nickname di chi crea la stanza")

class RoomResponse(BaseModel):
    """Risposta del server con i dettagli della stanza e il codice invito"""
    id: str
    codice_invito: str
    citta: str
    data: datetime
    occasione: Optional[str]
    scadenza: datetime
    organizzatore: str

    class Config:
        orm_mode = True  # Permette a Pydantic di leggere direttamente l'oggetto SQLAlchemy

# ==========================================
# MODELLI DI OUTPUT (Estratti dall'LLM)
# ==========================================

class ExtractedProfile(BaseModel):
    """Struttura dati che pretendiamo da Groq dopo l'analisi del testo (RF03)"""
    budget_max: Optional[float] = Field(
        None, description="Budget massimo in euro. Null se non specificato."
    )
    disponibile_da: Optional[str] = Field(
        None, description="Orario di inizio disponibilità nel formato HH:MM (es. '18:30')."
    )
    disponibile_a: Optional[str] = Field(
        None, description="Orario limite per il rientro nel formato HH:MM (es. '23:30')."
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
    mezzi_esclusi: List[str] = Field(
        default_factory=list, description="Mezzi che l'utente NON vuole o non può prendere (es. ['metro', 'piedi'])."
    )
    importanza_distanza: Optional[str] = Field(
        None, description="Quanto conta non allontanarsi. Valori: 'bassa', 'media', 'alta'."
    )
    preferenze_aggiuntive: List[str] = Field(
        default_factory=list, description="Desideri extra legati all'atmosfera, tipo di locale o servizi, inclusi suggerimenti su DOVE andare (es. 'musica dal vivo', 'romantico', 'tranquillo', 'al centro storico')."
    )
    
    # Questo campo implementa il requisito RF04 (Richiesta Chiarimento)
    richiesta_chiarimento: Optional[str] = Field(
        None, description="Domanda da porre all'utente in caso di contraddizioni logiche o luoghi incomprensibili."
    )

class LLMResponse(BaseModel):
    """Risposta standardizzata restituita al client dopo l'estrazione"""
    status: str = Field(..., description="'success' o 'clarification_needed'")
    profile: Optional[ExtractedProfile] = None
    message_to_user: Optional[str] = None