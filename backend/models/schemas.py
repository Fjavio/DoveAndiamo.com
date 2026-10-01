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
class FaseUscita(BaseModel):
    """Dettagli specifici per una singola tappa dell'uscita"""
    tipo_locale: Optional[str] = Field(None, description="Es. 'pizzeria', 'ristorante', 'pub', 'discoteca', 'bar', 'gelateria'.")
    budget: Optional[float] = Field(None, description="Budget dedicato esclusivamente a questa fase.")
    preferenze: List[str] = Field(default_factory=list, description="Atmosfera o desideri per questa fase (es. 'tranquillo', 'musica dal vivo').")

class ExtractedProfile(BaseModel):
    """Struttura dati evoluta per supportare il multi-tappa (RF03)"""
    
    # --- Gestione Tappe ---
    multi_tappa: bool = Field(False, description="True se l'utente vuole esplicitamente fare due cose (es. 'cena e poi drink').")
    budget_totale: Optional[float] = Field(None, description="Budget massimo per l'intera serata, se non lo divide per tappe.")
    tappa_1: Optional[FaseUscita] = Field(None, description="Dettagli della prima tappa (es. la cena). Valorizzato di default.")
    tappa_2: Optional[FaseUscita] = Field(None, description="Dettagli della seconda tappa (es. il dopocena). Null se vuole fare una sola cosa.")
    
    # --- Vincoli Globali (non cambiano tra una tappa e l'altra) ---
    disponibile_da: Optional[str] = Field(None, description="Orario di inizio HH:MM.")
    disponibile_a: Optional[str] = Field(None, description="Orario limite rientro HH:MM.")
    restrizioni_alimentari: List[str] = Field(default_factory=list, description="Es. ['vegetariano', 'celiaco'].")
    zona_partenza: Optional[str] = Field(None, description="Quartiere di partenza.")
    mezzo_trasporto: Optional[str] = Field(None)
    mezzi_esclusi: List[str] = Field(default_factory=list)
    importanza_distanza: Optional[str] = Field(None)
    
    richiesta_chiarimento: Optional[str] = Field(None, description="Domanda in caso di input incomprensibile o contraddittorio.")

class LLMResponse(BaseModel):
    """Risposta standardizzata restituita al client dopo l'estrazione"""
    status: str = Field(..., description="'success' o 'clarification_needed'")
    profile: Optional[ExtractedProfile] = None
    message_to_user: Optional[str] = None