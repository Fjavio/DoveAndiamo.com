import streamlit as st
import requests
from datetime import datetime, time

BASE_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="Jammo", layout="centered")

# --- GESTIONE DELLO STATO ---
if "vista_corrente" not in st.session_state:
    st.session_state.vista_corrente = "home"
if "stanza_attiva" not in st.session_state:
    st.session_state.stanza_attiva = None # Ora conterrà un dizionario: {"id":..., "codice":..., "nome":...}
if "mie_stanze" not in st.session_state:
    st.session_state.mie_stanze = [] # Ora conterrà dizionari, non più stringhe

def naviga_a(vista, stanza_data=None):
    st.session_state.vista_corrente = vista
    st.session_state.stanza_attiva = stanza_data

# ==========================================
# VISTA 1: HOME / DASHBOARD
# ==========================================
if st.session_state.vista_corrente == "home":
    st.title("JAMMO")
    
    col_crea, col_invito = st.columns([1, 1])
    
    with col_crea:
        st.button("➕ CREA STANZA", on_click=naviga_a, args=("crea_stanza",), use_container_width=True)
            
    with col_invito:
        with st.form("form_invito", clear_on_submit=True):
            codice = st.text_input("CODICE INVITO", label_visibility="collapsed", placeholder="Inserisci codice")
            btn_aggiungi = st.form_submit_button("Aggiungi alla lista")
            
            if btn_aggiungi and codice:
                with st.spinner("Ricerca stanza..."):
                    try:
                        response = requests.get(f"{BASE_URL}/rooms/code/{codice}")
                        if response.status_code == 200:
                            room_data = response.json()
                            # Definisce il nome da mostrare nel bottone
                            nome_display = room_data.get('occasione') or f"Uscita a {room_data.get('citta')}"
                            
                            # Verifica che non sia già in lista
                            if not any(s['codice'] == codice for s in st.session_state.mie_stanze):
                                st.session_state.mie_stanze.append({
                                    "id": room_data['id'],
                                    "codice": codice,
                                    "nome": nome_display
                                })
                                st.success(f"Aggiunta '{nome_display}' alle tue chat!")
                                st.rerun()
                            else:
                                st.info("Sei già in questa stanza.")
                        elif response.status_code == 404:
                            st.error("Stanza inesistente. Controlla il codice.")
                        else:
                            st.error(f"Errore di sistema: {response.text}")
                    except Exception as e:
                        st.error("Impossibile connettersi al Backend.")

    st.divider()
    
    with st.expander("STANZE", expanded=True):
        if not st.session_state.mie_stanze:
            st.info("Non sei ancora in nessuna stanza. Creane una o usa un codice invito.")
        else:
            for stanza in st.session_state.mie_stanze:
                # Layout per ogni riga: Bottone grande (nome) + Bottone piccolo (opzioni/codice)
                col_nome, col_opzioni = st.columns([4, 1])
                
                with col_nome:
                    st.button(
                        f"📁 {stanza['nome']}", 
                        key=f"btn_{stanza['codice']}", 
                        on_click=naviga_a, 
                        args=("dentro_stanza", stanza), 
                        use_container_width=True
                    )
                with col_opzioni:
                    # st.popover agisce come i "3 puntini", aprendo un menu sovrapposto
                    with st.popover("⚙️", use_container_width=True):
                        st.markdown("**Codice da condividere:**")
                        st.code(stanza['codice'], language=None)

# ==========================================
# VISTA 2: CREAZIONE STANZA
# ==========================================
elif st.session_state.vista_corrente == "crea_stanza":
    st.button("⬅️ Annulla e Torna Indietro", on_click=naviga_a, args=("home", None))
    st.title("Nuova Uscita")
    
    with st.form("form_crea_stanza"):
        citta = st.text_input("Città", value="Napoli")
        
        col1, col2 = st.columns(2)
        with col1:
            data_uscita = st.date_input("Data dell'uscita", min_value=datetime.today())
        with col2:
            ora_uscita = st.time_input("Ora indicativa", value=time(20, 30))
            
        occasione = st.text_input("Occasione (Opzionale)", placeholder="Es. Festa fine sessione")
        
        if st.form_submit_button("Genera Stanza", type="primary"):
            data_iso = f"{data_uscita}T{ora_uscita.strftime('%H:%M:%S')}"
            payload = {"citta": citta, "data": data_iso, "occasione": occasione}
            
            with st.spinner("Creazione in corso..."):
                try:
                    response = requests.post(f"{BASE_URL}/rooms/", json=payload)
                    if response.status_code == 200:
                        room_data = response.json()
                        nome_display = room_data.get('occasione') or f"Uscita a {room_data.get('citta')}"
                        
                        st.session_state.mie_stanze.append({
                            "id": room_data['id'],
                            "codice": room_data['codice_invito'],
                            "nome": nome_display
                        })
                        st.session_state.vista_corrente = "home"
                        st.rerun()
                    else:
                        st.error(f"Errore dal server: {response.text}")
                except Exception as e:
                    st.error("Impossibile connettersi al Backend.")

# ==========================================
# VISTA 3: DENTRO LA STANZA SELEZIONATA
# ==========================================
elif st.session_state.vista_corrente == "dentro_stanza":
    st.button("⬅️ Torna alle Stanze", on_click=naviga_a, args=("home", None))
    
    stanza_corrente = st.session_state.stanza_attiva
    st.title(f"📍 {stanza_corrente['nome']}")
    st.caption(f"Codice Invito: {stanza_corrente['codice']}")
    
    # Aggiungiamo il campo per il nome utente (necessario per il DB)
    nome_utente = st.text_input("Il tuo nome", placeholder="Es. Flavio")
    messaggio = st.text_area("Scrivi le tue esigenze per questa uscita:")
    
    if st.button("Invia Preferenze", type="primary"):
        if not nome_utente or not messaggio:
            st.warning("Inserisci il tuo nome e il messaggio prima di inviare.")
        else:
            payload_preferenze = {
                "user_id": nome_utente,
                "room_id": stanza_corrente['id'], # L'UUID alfanumerico nascosto
                "message": messaggio
            }
            
            with st.spinner("Il motore AI sta analizzando le tue preferenze... 🧠"):
                try:
                    response = requests.post(f"{BASE_URL}/users/extract-profile", json=payload_preferenze)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Gestione del Requisito RF04 (Chiarimento o Successo)
                        if data["status"] == "clarification_needed":
                            st.warning("⚠️ Manca un'informazione importante o c'è un'incongruenza:")
                            st.write(data["message_to_user"])
                        else:
                            st.success(f"🎯 {data['message_to_user']}")
                            st.json(data["profile"]) # Mostriamo il risultato a schermo
                    else:
                        st.error(f"Errore dal server: {response.text}")
                except Exception as e:
                    st.error("Impossibile connettersi al Backend. FastAPI è acceso?")