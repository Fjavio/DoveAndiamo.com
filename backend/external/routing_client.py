import os
import requests
from dotenv import load_dotenv

# Carica le variabili dal file .env nella memoria del sistema
load_dotenv()

# CACHE GLOBALE IN MEMORIA
_routing_cache = {}

class RoutingClient:
    """Boundary per il Routing Reale tramite Google Directions API (Pattern ECB)"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_ROUTING_API_KEY")

    def calcola_tempo_percorso(self, partenza: str, arrivo: str, citta: str) -> int:
        """
        Interroga Google Directions API per trovare il tempo di guida reale.
        """
        if not self.api_key or not partenza or not arrivo:
            return 20 # Fallback

        chiave_cache = f"{partenza}_{arrivo}_{citta}"
        if chiave_cache in _routing_cache:
            return _routing_cache[chiave_cache]
        
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{partenza}, {citta}",
                "destination": arrivo, # 'arrivo' qui è già l'indirizzo formattato da Google Places
                "mode": "driving",
                "language": "it",
                "key": self.api_key
            }
            
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            
            if data.get("status") == "OK" and data.get("routes"):
                # Google restituisce il tempo in secondi. Estraiamo il valore.
                leg = data["routes"][0]["legs"][0]
                secondi = leg["duration"]["value"]
                minuti = int(secondi / 60)
                # SALVO IN CACHE
                _routing_cache[chiave_cache] = minuti
                return minuti
                
        except Exception as e:
            print(f"Errore Google Directions API: {e}")
            
        return 20 # In caso di errore o traffico non calcolabile, stima 20 min