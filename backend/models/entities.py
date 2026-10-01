from sqlalchemy import Column, String, Float, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
import datetime
import uuid
from db.database import Base

class Stanza(Base):
    __tablename__ = "stanze"

    # Usiamo UUID per evitare di esporre ID sequenziali indovinabili
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    codice_invito = Column(String, unique=True, index=True, nullable=False)
    
    # Parametri generali decisi dall'organizzatore
    citta = Column(String, nullable=False)
    data = Column(DateTime, nullable=False)
    occasione = Column(String, nullable=True)
    scadenza = Column(DateTime, nullable=False)
    
    organizzatore = Column(String, nullable=False)

    # Relazione di COMPOSIZIONE: se muore la stanza, muoiono i partecipanti (Privacy GDPR)
    partecipanti = relationship("Partecipante", back_populates="stanza", cascade="all, delete-orphan")


class Partecipante(Base):
    __tablename__ = "partecipanti"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    stanza_id = Column(String, ForeignKey("stanze.id"), nullable=False)
    nome = Column(String, nullable=False)
    
    # --- Vincoli Globali ---
    disponibile_da = Column(String, nullable=True)
    disponibile_a = Column(String, nullable=True)
    zona_partenza = Column(String, nullable=True)
    mezzo_trasporto = Column(String, nullable=True)
    mezzi_esclusi = Column(JSON, default=list)
    importanza_distanza = Column(String, nullable=True) 
    restrizioni_alimentari = Column(JSON, default=list)
    
    # --- Nuovi Campi Multi-Tappa ---
    multi_tappa = Column(Boolean, default=False)
    budget_totale = Column(Float, nullable=True)
    tappa_1 = Column(JSON, nullable=True) # Conterrà il dizionario di FaseUscita
    tappa_2 = Column(JSON, nullable=True) # Conterrà il dizionario di FaseUscita
    
    stanza = relationship("Stanza", back_populates="partecipanti")