import os
import requests
from dotenv import load_dotenv

# Carica le variabili dal file .env nella memoria del sistema
load_dotenv()

# CACHE GLOBALE IN MEMORIA
_places_cache = {}

class PlacesDatabase:
    """Boundary per il reperimento di locali tramite Google Places API NEW (Pattern ECB)"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    
    def cerca_locali_tappa(self, citta: str, tipo_locale: str, preferenze_tappa: list, restrizioni_comuni: list, max_locali: int = 20):
        """
        Esegue una ricerca semantica mirata per una specifica fase della serata (es. solo cena o solo pub).
        """
        if not self.api_key:
            print("ATTENZIONE: Inserire la API Key di Google in places_db.py!")
            return []

        # Costruiamo la query semantica isolando le atmosfere di questa specifica tappa
        termini = []
        if tipo_locale:
            termini.append(tipo_locale)
        else:
            termini.append("locali ristoranti pub") # Fallback se l'utente non specifica il tipo
        
        if preferenze_tappa:
            termini.extend(preferenze_tappa)
            
        # Le restrizioni alimentari globali (es. celiachia) si applicano sempre a tutte le chiamate
        if restrizioni_comuni:
            termini.extend(restrizioni_comuni)
            
        testo_ricerca = f"{' '.join(termini)} a {citta}"

        # CONTROLLO CACHE
        chiave_cache = f"{citta}_{testo_ricerca}_{max_locali}"
        if chiave_cache in _places_cache:
            print(f"Hit Cache! Recupero locali per: {testo_ricerca}")
            return _places_cache[chiave_cache]

        url = "https://places.googleapis.com/v1/places:searchText"

        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.primaryType,places.types,places.regularOpeningHours"
        }
        """
        #places.location per ottenere coordinate e calcolare distanza reale tra locali
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.primaryType,places.types,places.regularOpeningHours,places.location"
        }
        
        payload = {
            "textQuery": testo_ricerca,
            "languageCode": "it",
            "maxResultCount": max_locali
        }
        
        locali_reali = []
        try:
            print(f"Richiesta a Google Places (NEW): {testo_ricerca}")
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if res.status_code == 200:
                places = res.json().get("places", [])
                
                for place in places:
                    nome = place.get("displayName", {}).get("text", "Locale Sconosciuto")
                    indirizzo = place.get("formattedAddress", citta)
                    location = place.get("location", {})
                    lat = location.get("latitude", 0.0)
                    lng = location.get("longitude", 0.0)
                    
                    livello_prezzo = place.get("priceLevel", "PRICE_LEVEL_MODERATE")
                    mappa_prezzi = {
                        "PRICE_LEVEL_INEXPENSIVE": 15,
                        "PRICE_LEVEL_MODERATE": 25,
                        "PRICE_LEVEL_EXPENSIVE": 50,
                        "PRICE_LEVEL_VERY_EXPENSIVE": 90,
                        "PRICE_LEVEL_UNSPECIFIED": 20
                    }
                    costo_medio = mappa_prezzi.get(livello_prezzo, 20)
                    
                    types = place.get("types", [])
                    primary_type = place.get("primaryType", "")
                    
                    tipo_effettivo = "pizzeria" if "pizza" in primary_type or "pizza" in nome.lower() else "pub" if "bar" in primary_type or "pub" in primary_type else "ristorante"
                    
                    orari_raw = place.get("regularOpeningHours", {}).get("periods", [])
                    
                    locali_reali.append({
                        "nome": nome,
                        "tipo": tipo_effettivo,
                        "zona": indirizzo,
                        "lat": lat,          
                        "lng": lng,      
                        "costo_medio": costo_medio,
                        "all_aperto": any(t in types for t in ["park", "campground", "zoo", "amusement_park"]),
                        "rating": place.get("rating", 0.0),
                        "orari_google": orari_raw
                    })

                _places_cache[chiave_cache] = locali_reali
            else:
                print(f"Errore dalla New API: {res.status_code}\n{res.text}")
                
        except Exception as e:
            print(f"Errore di connessione Google Places API (NEW): {e}")
            
        return locali_reali