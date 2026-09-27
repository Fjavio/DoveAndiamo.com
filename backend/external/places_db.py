import os
import requests
import random
from dotenv import load_dotenv

# Carica le variabili dal file .env nella memoria del sistema
load_dotenv()

class PlacesDatabase:
    """Boundary per il reperimento di locali tramite Google Places API NEW (Pattern ECB)"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    
    def get_all_places(self, citta: str, desideri_extra: str = "", max_locali: int = 20):
        if not self.api_key:
            print("ATTENZIONE: Inserire la API Key di Google in places_db.py!")
            return []

        # 1. Costruiamo la query semantica per la New API
        if desideri_extra:
            testo_ricerca = f"ristoranti locali {desideri_extra} a {citta}"
        else:
            testo_ricerca = f"migliori ristoranti pub pizzerie a {citta}"

        # Endpoint della versione NEW
        url = "https://places.googleapis.com/v1/places:searchText"
        
        # La nuova API richiede esplicitamente di dichiarare quali campi vogliamo (FieldMask)
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.rating,places.primaryType,places.types"
        }
        
        payload = {
            "textQuery": testo_ricerca,
            "languageCode": "it",
            "maxResultCount": max_locali
        }
        
        locali_reali = []
        try:
            print(f"Richiesta a Google Places (NEW): {testo_ricerca}")
            # La New API usa il metodo POST
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if res.status_code == 200:
                places = res.json().get("places", [])
                
                for place in places:
                    # La struttura JSON della New API è diversa
                    nome = place.get("displayName", {}).get("text", "Locale Sconosciuto")
                    indirizzo = place.get("formattedAddress", citta)
                    
                    # La New API restituisce stringhe per i prezzi, non più numeri da 0 a 4
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
                    
                    tipo = "ristorante"
                    if "pizza" in primary_type or "pizza" in nome.lower():
                        tipo = "pizzeria"
                    elif "bar" in primary_type or "pub" in primary_type:
                        tipo = "pub"
                        
                    # Logica di stubbing/mocking per faciltare i test
                    """
                    menu = ["normale"]
                    if "vegan" in nome.lower() or "veg" in nome.lower() or "healthy" in primary_type:
                        menu.extend(["vegano", "vegetariano"])
                    elif tipo == "pizzeria":
                        menu.append("vegetariano")
                    
                    # Aggiunta probabilistica per non svuotare mai del tutto le opzioni
                    if random.random() > 0.4: menu.append("vegano")
                    if random.random() > 0.3: menu.append("vegetariano")
                    if random.random() > 0.5: menu.append("celiaci")
                    """

                    # Logica reale: Deleghiamo la scrematura dietetica alla ricerca semantica a monte
                    menu = []

                    locali_reali.append({
                        "nome": nome,
                        "tipo": tipo,
                        "zona": indirizzo,
                        "costo_medio": costo_medio,
                        "all_aperto": "park" in types or random.random() > 0.7,
                        "menu": menu,
                        "rating": place.get("rating", 0.0)
                    })
            else:
                print(f"Errore dalla New API: {res.status_code} - {res.text}")
                
        except Exception as e:
            print(f"Errore di connessione Google Places API (NEW): {e}")
            
        return locali_reali