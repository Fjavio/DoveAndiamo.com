# DoveAndiamo.com
STRUTTURA AD ALBERO:
jammo_project/
├── docker-compose.yml           # (RNF11) Avvia tutto l'ecosistema
├── .env                         # Chiavi API (Groq, Meteo, Maps)
│
├── frontend/                    # (Streamlit)
│   ├── Dockerfile
│   ├── app.py                   # Entry point interfaccia utente
│   ├── components/              # Widget UI riutilizzabili (chat, mappe)
│   └── api_client.py            # Modulo per chiamare le rotte di FastAPI
│
└── backend/                     # (FastAPI)
    ├── Dockerfile
    ├── main.py                  # Entry point FastAPI, inizializzazione app
    ├── requirements.txt
    │
    ├── api/                     # Controller delle rotte (RF01, RF02, RF06)
    │   ├── room_routes.py       # POST /rooms, GET /rooms/{id}
    │   └── user_routes.py       # POST /rooms/{id}/preferences
    │
    ├── core/                    # Logica di orchestrazione
    │   ├── orchestrator.py      # Il "motore centrale" che unisce LLM, Mappe e DB
    │   └── solver.py            # (RNF1) Validatore deterministico dei vincoli rigidi
    │
    ├── llm/                     # Isolamento del Provider LLM (Groq)
    │   ├── extractor.py         # (RF03, RF04, RNF2) Estrazione JSON e Self-Reflection
    │   ├── compromiser.py       # (RF10) Calcolo del compromesso e spiegazione testuale
    │   └── prompts/             # Template testuali per le istruzioni di sistema
    │
    ├── external/                # Adapter per i servizi terzi
    │   ├── weather_client.py    # (RF08) Chiamate a OpenWeather
    │   ├── routing_client.py    # (RF09) Chiamate a OpenRouteService per tempi e distanze
    │   └── places_db.py         # (RF07) Interazione con ChromaDB per filtrare i locali
    │
    ├── models/                  # Definizione delle strutture dati
    │   ├── schemas.py           # Modelli Pydantic per validare i JSON in entrata/uscita
    │   └── entities.py          # Modelli ORM per il salvataggio su database relazionale
    │
    └── workers/
        └── cleanup_task.py      # (RF11, RNF3) Job in background per cancellare le stanze scadute

        
Installazione pacchetti:

Scarica i Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/ e clicca su "Scarica Build Tools".

Avvia l'installer: Apri il file .exe appena scaricato.

Seleziona il pacchetto: Nella schermata principale dell'installer, metti la spunta sulla casella "Sviluppo per desktop con C++" (in inglese Desktop development with C++). Sulla destra vedrai che selezionerà in automatico alcuni pacchetti (tra cui MSVC v143 e l'SDK di Windows 10/11). Lasciali così.

Installa: Clicca su Installa in basso a destra

Una volta finita l'installazione, chiudi completamente VS Code (o il terminale PowerShell che stai usando) e riaprilo.

In cartella backend, riattiva l'ambiente e lancia di nuovo: pip install -r requirements.txt