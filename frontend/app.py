import streamlit as st
import requests
from datetime import datetime, time

BASE_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="Jammo", layout="centered")

# --- GESTIONE DELLO STATO ---
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None  # Se è None, mostriamo la schermata di Login
if "vista_corrente" not in st.session_state:
    st.session_state.vista_corrente = "home"
if "stanza_attiva" not in st.session_state:
    st.session_state.stanza_attiva = None
if "mie_stanze" not in st.session_state:
    st.session_state.mie_stanze = [] 
if "messaggio_toast" not in st.session_state:
    st.session_state.messaggio_toast = None

def naviga_a(vista, stanza_data=None):
    st.session_state.vista_corrente = vista
    st.session_state.stanza_attiva = stanza_data

def esegui_logout():
    # Pulisce la sessione e riporta al login
    st.session_state.utente_loggato = None
    st.session_state.mie_stanze = []
    st.session_state.vista_corrente = "home"

# ==========================================
# VISTA 0: LOGIN (Schermata di Accesso)
# ==========================================
if st.session_state.utente_loggato is None:
    st.title("👋 Benvenuto in Jammo")
    st.markdown("Effettua l'accesso per iniziare a organizzare le tue uscite.")
    
    with st.form("login_form"):
        nickname = st.text_input("Il tuo Nickname", placeholder="Es. Flavio")
        submit_login = st.form_submit_button("Accedi", type="primary")
        
        if submit_login:
            if nickname.strip():
                st.session_state.utente_loggato = nickname.strip()
                # CHIAMATA AL DB: Recupera le stanze salvate per questo utente
                try:
                    res = requests.get(f"{BASE_URL}/users/{nickname.strip()}/rooms")
                    if res.status_code == 200:
                        st.session_state.mie_stanze = res.json()
                except Exception:
                    pass

                st.rerun()
            else:
                st.error("Inserisci un nickname valido.")

else:
    # --- HEADER AUTENTICATO ---
    # Mostriamo sempre chi è l'utente corrente e diamo la possibilità di disconnettersi
    col_user, col_logout = st.columns([4, 1])
    with col_user:
        st.markdown(f"👤 Connesso come: **{st.session_state.utente_loggato}**")
    with col_logout:
        st.button("🚪 Esci", on_click=esegui_logout, use_container_width=True)
        
    st.divider()

    # ==========================================
    # VISTA 1: HOME / DASHBOARD
    # ==========================================
    if st.session_state.vista_corrente == "home":

        if st.session_state.messaggio_toast:
            st.toast(st.session_state.messaggio_toast, icon="✅")
            st.session_state.messaggio_toast = None

        st.title("JAMMO")

        col_crea, col_invito = st.columns([1, 1])
        
        with col_crea:
            st.button("➕ CREA STANZA", on_click=naviga_a, args=("crea_stanza",), use_container_width=True)
                
        with col_invito:
            with st.form("form_invito", clear_on_submit=True):
                codice = st.text_input("CODICE INVITO", label_visibility="collapsed", placeholder="Inserisci codice")
                btn_aggiungi = st.form_submit_button("Aggiungi alla lista")
                
                if btn_aggiungi and codice:
                    with st.spinner("Ricerca e aggiunta..."):
                        try:
                            # CHIAMATA AL DB: Associa permanentemente l'utente alla stanza
                            res = requests.post(f"{BASE_URL}/users/{st.session_state.utente_loggato}/join/{codice}")
                            
                            if res.status_code == 200:
                                stanza_data = res.json()
                                if not any(s['codice'] == codice for s in st.session_state.mie_stanze):
                                    st.session_state.mie_stanze.append(stanza_data)
                                    st.session_state.messaggio_toast = f"Aggiunta '{stanza_data['nome']}'!"
                                    st.rerun()
                                else:
                                    st.info("Sei già in questa stanza.")
                            elif res.status_code == 404:
                                st.error("Stanza inesistente. Controlla il codice.")
                        except Exception:
                            st.error("Errore di connessione.")

        st.divider()
        
        with st.expander("STANZE", expanded=True):
            if not st.session_state.mie_stanze:
                st.info("Non sei ancora in nessuna stanza. Creane una o usa un codice invito.")
            else:
                for stanza in st.session_state.mie_stanze:
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
                payload = {"citta": citta, "data": data_iso, "occasione": occasione, "creatore": st.session_state.utente_loggato}
                
                with st.spinner("Creazione in corso..."):
                    try:
                        # Crea la stanza
                        response = requests.post(f"{BASE_URL}/rooms/", json=payload)
                        if response.status_code == 200:
                            room_data = response.json()
                            codice_generato = room_data['codice_invito']
                            
                            # Associa il creatore come partecipante nel DB
                            requests.post(f"{BASE_URL}/users/{st.session_state.utente_loggato}/join/{codice_generato}")
                            
                            # Ricarica le stanze dal DB per la sessione aggiornata
                            res_stanze = requests.get(f"{BASE_URL}/users/{st.session_state.utente_loggato}/rooms")
                            if res_stanze.status_code == 200:
                                st.session_state.mie_stanze = res_stanze.json()
                            
                            st.session_state.vista_corrente = "home"
                            st.session_state.messaggio_toast = "Stanza creata con successo!"
                            st.rerun()
                        else:
                            st.error(f"Errore dal server: {response.text}")
                    except Exception:
                        st.error("Impossibile connettersi al Backend.")

    # ==========================================
    # VISTA 3: DENTRO LA STANZA SELEZIONATA
    # ==========================================
    elif st.session_state.vista_corrente == "dentro_stanza":
        st.button("⬅️ Torna alle Stanze", on_click=naviga_a, args=("home", None))
        
        stanza_corrente = st.session_state.stanza_attiva
        st.title(f"📍 {stanza_corrente['nome']}")
        st.caption(f"Codice Invito: {stanza_corrente['codice']}")
        
        # --- RECUPERO PARTECIPANTI ---
        st.markdown("### 👥 Chi c'è in questa stanza")
        try:
            res_part = requests.get(f"{BASE_URL}/rooms/{stanza_corrente['id']}/participants")
            if res_part.status_code == 200:
                partecipanti = res_part.json()
                if not partecipanti:
                    st.info("Nessuno ha ancora inserito le proprie preferenze. Inizia tu!")
                else:
                    """
                    for p in partecipanti:
                        with st.expander(f"👤 {p['nome']}"):
                            # Adattiamo il budget al nuovo modello
                            budget = p.get('budget_totale') or p.get('budget_max') or 'N/D'
                            st.write(f"**Budget Serata:** {budget} €")
                            st.write(f"**Disponibilità:** {p.get('disponibile_da', 'N/D')} - {p.get('disponibile_a', 'N/D')}")
                            st.write(f"**Zona:** {p.get('zona_partenza', 'N/D')}")
                            st.write(f"**Restrizioni:** {', '.join(p.get('restrizioni_alimentari', [])) or 'Nessuna'}")
                            
                            # NUOVO: Mostriamo l'intento Multi-Tappa
                            if p.get('multi_tappa'):
                                t1 = p.get('tappa_1', {})
                                t2 = p.get('tappa_2', {})
                                pref_t1 = ", ".join(t1.get('preferenze', [])) or "Nessuna specifica"
                                pref_t2 = ", ".join(t2.get('preferenze', [])) or "Nessuna specifica"
                                
                                st.info(
                                    f"🔄 **Vuole fare due tappe!**\n\n"
                                    f"🍕 **Fase 1 ({t1.get('tipo_locale', 'Pasto')}):** {pref_t1}\n\n"
                                    f"🍻 **Fase 2 ({t2.get('tipo_locale', 'Dopocena')}):** {pref_t2}"
                                )
                    """
                    for p in partecipanti:
                        with st.expander(f"👤 {p['nome']}"):
                            # PRIVACY CHECK: Questo utente è quello correntemente loggato? Mostriamo i suoi dati sensibili solo a lui
                            is_me = (p['nome'] == st.session_state.utente_loggato)
                            
                            # BUDGET (Dato sensibile)
                            if is_me:
                                budget = p.get('budget_totale') or p.get('budget_max') or 'N/D'
                                st.write(f"**Budget Serata:** {budget} €")
                            else:
                                st.write("**Budget Serata:** 🔒 *Nascosto per privacy*")
                            
                            # ORARI E ZONA (Dati logistici, visibili al gruppo per organizzarsi)
                            st.write(f"**Disponibilità:** {p.get('disponibile_da', 'N/D')} - {p.get('disponibile_a', 'N/D')}")
                            st.write(f"**Zona:** {p.get('zona_partenza', 'N/D')}")
                            
                            # RESTRIZIONI ALIMENTARI (Dato sensibile)
                            if is_me:
                                st.write(f"**Restrizioni:** {', '.join(p.get('restrizioni_alimentari', [])) or 'Nessuna'}")
                            else:
                                if p.get('restrizioni_alimentari'):
                                    st.write("**Restrizioni:** 🔒 *Presenti ma nascoste*")
                                else:
                                    st.write("**Restrizioni:** Nessuna")
                            
                            # Mostriamo l'intento Multi-Tappa
                            if p.get('multi_tappa'):
                                t1 = p.get('tappa_1', {})
                                t2 = p.get('tappa_2', {})
                                pref_t1 = ", ".join(t1.get('preferenze', [])) or "Nessuna specifica"
                                pref_t2 = ", ".join(t2.get('preferenze', [])) or "Nessuna specifica"
                                
                                st.info(
                                    f"🔄 **Vuole fare due tappe!**\n\n"
                                    f"🍕 **Fase 1 ({t1.get('tipo_locale', 'Pasto')}):** {pref_t1}\n\n"
                                    f"🍻 **Fase 2 ({t2.get('tipo_locale', 'Dopocena')}):** {pref_t2}"
                                )
        except Exception:
            st.warning("Impossibile caricare i partecipanti.")

        st.divider()
        
        # --- FORM DI INSERIMENTO (LLM) ---
        st.markdown("### ✍️ Aggiungi le tue preferenze")
        
        # IL CAMPO NOME È STATO RIMOSSO!
        messaggio = st.text_area("Scrivi le tue esigenze (orari, budget, intolleranze...):")
        
        if st.button("Invia Preferenze", type="primary"):
            if not messaggio:
                st.warning("Devi scrivere un messaggio prima di inviare.")
            else:
                # Usiamo l'identità salvata nella sessione per il payload
                payload_preferenze = {
                    "user_id": st.session_state.utente_loggato,
                    "room_id": stanza_corrente['id'],
                    "message": messaggio
                }
                with st.spinner("Il motore AI sta analizzando le tue preferenze... 🧠"):
                    try:
                        response = requests.post(f"{BASE_URL}/users/extract-profile", json=payload_preferenze)
                        if response.status_code == 200:
                            data = response.json()
                            if data["status"] == "clarification_needed":
                                st.warning("⚠️ " + data["message_to_user"])
                            else:
                                # Prepariamo il messaggio a scomparsa
                                st.session_state.messaggio_toast = "Preferenze inviate con successo!"
                                # Riportiamo l'utente alla schermata principale
                                st.session_state.vista_corrente = "home"
                                # Ricarichiamo l'app
                                st.rerun()
                        else:
                            st.error("Errore dal server.")
                    except Exception:
                        st.error("Impossibile connettersi al Backend.")

        # --- SEZIONE ORGANIZZATORE ---
        if stanza_corrente.get('organizzatore') == st.session_state.utente_loggato:
            st.divider()
            st.markdown("### 👑 Pannello Organizzatore")
            if st.button("🪄 Calcola Itinerario Reale", type="primary", use_container_width=True):
                with st.spinner("Incrocio vincoli, controllo meteo e calcolo stradale in corso..."):
                    try:
                        res_solver = requests.get(f"{BASE_URL}/rooms/{stanza_corrente['id']}/proposals")
                        if res_solver.status_code == 200:
                            dati = res_solver.json()
                            
                            st.success("Calcolo completato!")
                            st.markdown("## 🎯 La Proposta di Jammo")

                            #messaggio spiegativo del LLM
                            st.info(f"🤖 **Jammo dice:**\n\n*{dati.get('messaggio_ia', '')}*")
                            
                            # Resoconto dei Vincoli
                            vincoli = dati.get('vincoli_gruppo', {})
                            
                            # Se i vincoli sono stati rilassati, mostriamo il messaggio di compromesso
                            if vincoli.get('vincoli_rilassati'):
                                st.warning(dati.get('esito'))
                                budget_mostrato = f"{vincoli['budget_cap']}€ (lievemente superato per trovare opzioni valide)"
                            else:
                                budget_mostrato = f"{vincoli['budget_cap']}€"

                            st.info(
                                f"⏱️ **Si esce alle:** {vincoli['orario_comune']['da']}\n\n"
                                f"💰 **Budget Max concordato:** {budget_mostrato}\n\n"
                                f"🥗 **Diete/Intolleranze rispettate:** {', '.join(vincoli['restrizioni']).capitalize() or 'Nessuna'}\n\n"
                                f"🌧️ **Meteo previsto:** {'Pioverà (Locali all\'aperto esclusi)' if vincoli['piovera'] else 'Sereno'}"
                            )
                            
                            # Risultati Locali
                            locali = dati.get('locali_proposti', [])
                            if not locali:
                                st.error("😭 **Nessun locale trovato!** I vincoli incrociati sono troppo stringenti (neanche allentando il budget si sono trovate opzioni).")
                            else:
                                st.markdown("### 🏆 I migliori locali per voi:")
                                for i, loc in enumerate(locali[:3]): 
                                    with st.container(border=True):
                                        st.markdown(f"#### {i+1}. {loc['nome']} ({loc['tipo'].capitalize()})")
                                        st.write(f"📍 **Zona:** {loc['zona']} | 💸 **Costo stimato:** {loc['costo_medio']}€")
                                        testo_distanza = f"{loc['minuti_di_guida']} minuti di guida" if loc['minuti_di_guida'] > 0 else "N/D (Punti di partenza non specificati)"
                                        st.caption(f"🚗 Distanza massima: {testo_distanza}")
                        else:
                            st.error(f"Errore: {res_solver.text}")
                    except Exception:
                        st.error("Impossibile contattare il Solver.")