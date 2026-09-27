from datetime import datetime
from typing import List, Dict
from external.places_db import PlacesDatabase
from external.weather_client import WeatherClient
from external.routing_client import RoutingClient

class ItinerarySolver:
    """
    Classe Control (Pattern ECB) responsabile del calcolo dell'itinerario.
    Risolve le intersezioni tra i vincoli dei partecipanti e filtra i locali candidati.
    """
    def __init__(self):
        self.places_db = PlacesDatabase()
        self.weather_client = WeatherClient()
        self.routing_client = RoutingClient()

    def _calcola_intersezione_orari(self, stanza: any, partecipanti: List[any]) -> Dict[str, str]:
        #Trova l'intervallo di tempo in cui TUTTI sono disponibili

        # Prende l'orario impostato dall'organizzatore come default
        orario_base = stanza.data.strftime("%H:%M")

        #Se non ci sono orari, impostiamo default larghi
        max_start = "00:00"
        min_end = "23:59"
        ha_vincoli = False
        
        for p in partecipanti:
            if p.disponibile_da:
                max_start = max(max_start, p.disponibile_da)
                ha_vincoli = True
            if p.disponibile_a:
                min_end = min(min_end, p.disponibile_a)
                ha_vincoli = True

        # Se nessuno ha espresso preferenze di orario, usiamo quello della stanza
        if not ha_vincoli:
            return {"da": orario_base, "a": "Nessun limite"}
        
        # Se max_start è maggiore di min_end, l'intersezione è impossibile
        if max_start >= min_end:
            return None 
        return {"da": max_start, "a": min_end}

    def _calcola_budget_gruppo(self, partecipanti: List[any]) -> float:
        #Trova il budget massimo accettabile per il gruppo = il budget del più "povero"
        budget_min = 9999.0
        for p in partecipanti:
            if p.budget_max and p.budget_max < budget_min:
                budget_min = p.budget_max
        return budget_min if budget_min != 9999.0 else None

    def _estrai_restrizioni_comuni(self, partecipanti: List[any]) -> List[str]:
        #Raccoglie tutte le intolleranze o diete del gruppo per filtrare il menu
        restrizioni = set()
        for p in partecipanti:
            if p.restrizioni_alimentari:
                # Gestisce sia liste che stringhe separate da virgola (in base a come le ha estratte l'LLM)
                if isinstance(p.restrizioni_alimentari, list):
                    restrizioni.update([r.lower() for r in p.restrizioni_alimentari])
        return list(restrizioni)

    """
    def elabora_proposta(self, stanza: any, partecipanti: List[any]) -> Dict:
        # Calcolo Vincoli di Gruppo
        orari_comuni = self._calcola_intersezione_orari(stanza, partecipanti)
        budget_max = self._calcola_budget_gruppo(partecipanti)
        restrizioni = self._estrai_restrizioni_comuni(partecipanti)

        # Estraiamo tutti i "desideri" (es. romantico, musica) per fare una ricerca mirata
        desideri = set()
        for p in partecipanti:
            if p.preferenze_aggiuntive:
                desideri.update(p.preferenze_aggiuntive)
        query_desideri = " ".join(desideri)

        # Chiamata Servizi Esterni
        pioverà = self.weather_client.check_rain(stanza.citta, stanza.data)
        locali_candidati = self.places_db.get_all_places(stanza.citta, desideri_extra=query_desideri)
        
        # Filtraggio - PRIMA PASSATA (Vincoli Rigidi)
        locali_validi_strict = []
        for locale in locali_candidati:
            # Meteo (Intoccabile)
            if pioverà and locale.get("all_aperto"): continue
            # Diete (Intoccabili)
            menu_locale = [m.lower() for m in locale.get("menu", [])]
            if "vegano" in restrizioni and "vegano" not in menu_locale: continue
            if "vegetariano" in restrizioni and ("vegetariano" not in menu_locale and "vegano" not in menu_locale): continue
            if "celiaco" in restrizioni and "celiaci" not in menu_locale: continue
            
            # Budget Rigido
            if budget_max and locale.get("costo_medio", 0) > budget_max:
                continue 
                
            locali_validi_strict.append(locale)

        vincoli_rilassati = False
        messaggio_compromesso = "Calcolo completato nel rispetto di tutti i vincoli."
        locali_finali = locali_validi_strict

        # Filtraggio - SECONDA PASSATA (Rilassamento Vincolo Budget)
        # Se la prima passata ha fallito, allentiamo il budget del 20%
        if not locali_validi_strict and budget_max:
            budget_tollerato = budget_max * 1.20 # +20% di tolleranza
            locali_validi_relax = []
            
            for locale in locali_candidati:
                if pioverà and locale.get("all_aperto"): continue
                menu_locale = [m.lower() for m in locale.get("menu", [])]
                if "vegano" in restrizioni and "vegano" not in menu_locale: continue
                if "vegetariano" in restrizioni and ("vegetariano" not in menu_locale and "vegano" not in menu_locale): continue
                if "celiaco" in restrizioni and "celiaci" not in menu_locale: continue
                
                # Applichiamo il Budget Rilassato
                if locale.get("costo_medio", 0) <= budget_tollerato:
                    locali_validi_relax.append(locale)

            if locali_validi_relax:
                locali_finali = locali_validi_relax
                vincoli_rilassati = True
                messaggio_compromesso = "⚠️ È stato necessario applicare un piccolo compromesso economico rispetto al budget più basso per trovare opzioni valide adatte alle restrizioni alimentari del gruppo."

        # Aggiunta dei tempi di percorrenza
        for locale in locali_finali:
            tempi = []
            for p in partecipanti:
                if p.zona_partenza:
                    minuti = self.routing_client.calcola_tempo_percorso(p.zona_partenza, locale["zona"], stanza.citta)
                    tempi.append(minuti)
            locale["minuti_di_guida"] = max(tempi) if tempi else 0

        # Ordinamento (i più vicini per tutti)
        locali_finali.sort(key=lambda x: x.get("minuti_di_guida", 999))

        return {
            "vincoli_gruppo": {
                "orario_comune": orari_comuni,
                "budget_cap": budget_max,
                "restrizioni": restrizioni,
                "desideri_soddisfatti": list(desideri),
                "piovera": pioverà,
                "vincoli_rilassati": vincoli_rilassati # Flag per il frontend
            },
            "locali_proposti": locali_finali,
            "esito": messaggio_compromesso
        }
    """

    def elabora_proposta(self, stanza: any, partecipanti: List[any]) -> Dict:
        # 1. Calcolo Vincoli di Gruppo
        orari_comuni = self._calcola_intersezione_orari(stanza, partecipanti)
        budget_max = self._calcola_budget_gruppo(partecipanti)
        restrizioni = self._estrai_restrizioni_comuni(partecipanti)
        
        # Uniamo desideri e restrizioni dietetiche per il motore semantico di Google
        desideri = set()
        for p in partecipanti:
            if p.preferenze_aggiuntive:
                desideri.update(p.preferenze_aggiuntive)
        
        # Aggiungiamo esplicitamente le diete alla query di ricerca
        termini_ricerca = list(desideri) + restrizioni
        query_desideri = " ".join(termini_ricerca)
        
        # 2. Chiamata Servizi Esterni
        pioverà = self.weather_client.check_rain(stanza.citta, stanza.data)
        locali_candidati = self.places_db.get_all_places(stanza.citta, desideri_extra=query_desideri)
        
        # 3. Filtraggio - PRIMA PASSATA (Solo Vincoli Matematici Rigidi)
        locali_validi_strict = []
        for locale in locali_candidati:
            # Meteo (Intoccabile)
            if pioverà and locale.get("all_aperto"): continue
            
            # Budget Rigido
            if budget_max and locale.get("costo_medio", 0) > budget_max:
                continue 
                
            locali_validi_strict.append(locale)

        vincoli_rilassati = False
        messaggio_compromesso = "Calcolo completato nel rispetto di tutti i vincoli."
        locali_finali = locali_validi_strict

        # 4. Filtraggio - SECONDA PASSATA (Rilassamento Vincolo Budget)
        if not locali_validi_strict and budget_max:
            budget_tollerato = budget_max * 1.20 
            locali_validi_relax = []
            
            for locale in locali_candidati:
                if pioverà and locale.get("all_aperto"): continue
                
                if locale.get("costo_medio", 0) <= budget_tollerato:
                    locali_validi_relax.append(locale)

            if locali_validi_relax:
                locali_finali = locali_validi_relax
                vincoli_rilassati = True
                messaggio_compromesso = "⚠️ È stato necessario applicare un piccolo compromesso economico per trovare opzioni compatibili con tutte le vostre richieste."

        # 5. Aggiunta dei tempi di percorrenza
        for locale in locali_finali:
            tempi = []
            for p in partecipanti:
                if p.zona_partenza:
                    minuti = self.routing_client.calcola_tempo_percorso(p.zona_partenza, locale["zona"], stanza.citta)
                    tempi.append(minuti)
            locale["minuti_di_guida"] = max(tempi) if tempi else 0

        # 6. Ordinamento (i più vicini per tutti)
        locali_finali.sort(key=lambda x: x.get("minuti_di_guida", 999))

        return {
            "vincoli_gruppo": {
                "orario_comune": orari_comuni,
                "budget_cap": budget_max,
                "restrizioni": restrizioni,
                "desideri_soddisfatti": termini_ricerca, 
                "piovera": pioverà,
                "vincoli_rilassati": vincoli_rilassati
            },
            "locali_proposti": locali_finali,
            "esito": messaggio_compromesso
        }