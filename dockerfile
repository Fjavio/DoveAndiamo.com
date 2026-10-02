# Usa un'immagine Python ufficiale e leggera
FROM python:3.12-slim

# Imposta la cartella di lavoro all'interno del container
WORKDIR /app

# Installa le dipendenze di sistema necessarie (es. per SQLite e compilazione)
RUN apt-get update && \
    apt-get install -y gcc sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Copia il file dei requisiti e installa le librerie
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice del progetto
COPY . .