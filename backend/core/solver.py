from datetime import datetime, date
from typing import List, Dict
import itertools
from external.places_db import PlacesDatabase
from external.weather_client import WeatherClient
from external.routing_client import RoutingClient
import math

class ItinerarySolver:
    """
    Classe Control (Pattern ECB) responsabile del calcolo dell'itinerario.
    Ora supporta il Prodotto Cartesiano per itinerari Multi-Tappa.
    """
    def __init__(self):
        self.places_db = PlacesDatabase()
        self.weather_client = WeatherClient()
        self.routing_client = RoutingClient()

    def _calcola_intersezione_orari(self, stanza: any, partecipanti: List[any]) -> Dict[str, str]:
        orario_base = stanza.data.strftime("%H:%M")
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

        if not ha_vincoli:
            return {"da": orario_base, "a": "Nessun limite"}
        if max_start >= min_end:
            return None 
        return {"da": max_start, "a": min_end}

    def _calcola_budget_gruppo(self, partecipanti: List[any]) -> float:
        budget_min = 9999.0
        for p in partecipanti:
            # Sfruttiamo il nuovo campo budget_totale se esiste, altrimenti il fallback sul vecchio budget_max
            b = p.budget_totale or p.budget_max
            if b and b < budget_min:
                budget_min = b
        return budget_min if budget_min != 9999.0 else None

    def _estrai_restrizioni_comuni(self, partecipanti: List[any]) -> List[str]:
        restrizioni = set()
        for p in partecipanti:
            if p.restrizioni_alimentari:
                if isinstance(p.restrizioni_alimentari, list):
                    restrizioni.update([r.lower() for r in p.restrizioni_alimentari])
        return list(restrizioni)

    def elabora_proposta(self, stanza: any, partecipanti: List[any]) -> Dict:
        # 1. VINCOLI GLOBALI
        orari_comuni = self._calcola_intersezione_orari(stanza, partecipanti)
        budget_max = self._calcola_budget_gruppo(partecipanti)
        restrizioni = self._estrai_restrizioni_comuni(partecipanti)
        pioverà = self.weather_client.check_rain(stanza.citta, stanza.data)
        
        # 2. RILEVAMENTO MODALITÀ (Singola vs Multi-Tappa)
        is_multi = any(p.multi_tappa for p in partecipanti)
        
        pref_t1, pref_t2 = set(), set()
        tipo_t1, tipo_t2 = None, None
        
        # Estrazione aggregata per le due fasi
        for p in partecipanti:
            if p.tappa_1:
                if p.tappa_1.get("preferenze"): pref_t1.update(p.tappa_1["preferenze"])
                if not tipo_t1 and p.tappa_1.get("tipo_locale"): tipo_t1 = p.tappa_1["tipo_locale"]
            if p.tappa_2:
                if p.tappa_2.get("preferenze"): pref_t2.update(p.tappa_2["preferenze"])
                if not tipo_t2 and p.tappa_2.get("tipo_locale"): tipo_t2 = p.tappa_2["tipo_locale"]
                
        if not tipo_t1: tipo_t1 = "ristorante"
        if is_multi and not tipo_t2: tipo_t2 = "pub"
        
        # 3. GENERAZIONE DEL POOL (Chiamate API Isolate)
        locali_t1 = self.places_db.cerca_locali_tappa(stanza.citta, tipo_t1, list(pref_t1), restrizioni)
        
        ora_in = orari_comuni.get("da", "20:00") if orari_comuni else "20:00"
        locali_t1 = [l for l in locali_t1 if not (pioverà and l.get("all_aperto")) and self._is_locale_aperto(l.get("orari_google", []), stanza.data, str(ora_in), "Nessun limite")]
        
        locali_finali = []
        vincoli_rilassati = False
        messaggio_compromesso = "Calcolo completato nel rispetto di tutti i vincoli incrociati."
        termini_soddisfatti = list(pref_t1) + list(pref_t2)
        
        # 4. MOTORE MATEMATICO
        if not is_multi:
            # --- LOGICA SINGOLA TAPPA ---
            for loc in locali_t1:
                if budget_max and loc["costo_medio"] > budget_max: continue
                locali_finali.append(loc)
                
            if not locali_finali and budget_max: # Graceful Degradation sul budget
                budget_tollerato = budget_max * 1.2
                locali_finali = [l for l in locali_t1 if l["costo_medio"] <= budget_tollerato]
                if locali_finali:
                    vincoli_rilassati = True
                    messaggio_compromesso = "⚠️ Applicato lieve compromesso economico sul budget."
                    
        else:
            # --- LOGICA MULTI-TAPPA (ESPLOSIONE COMBINATORIA) ---
            # La tappa 2 (es. cocktail bar) non richiede il filtro delle restrizioni alimentari severe
            locali_t2 = self.places_db.cerca_locali_tappa(stanza.citta, tipo_t2, list(pref_t2), []) 
            locali_t2 = [l for l in locali_t2 if not (pioverà and l.get("all_aperto"))]
            
            combinazioni = list(itertools.product(locali_t1, locali_t2))
            
            # Calcolo dinamico della Timeline Concatenata (stimiamo 2 ore per la Tappa 1)
            h_in, m_in = map(int, str(ora_in).split(":"))
            h_in_t2 = (h_in + 2) % 24
            ora_in_t2 = f"{h_in_t2:02d}:{m_in:02d}"
            
            combinazioni_valide = []
            for loc1, loc2 in combinazioni:
                # Filtro Haversine: Scarta a priori i locali distanti più di 3.5 km in linea d'aria
                if loc1.get("lat") and loc2.get("lat"):
                    distanza_km = self._calcola_distanza_haversine(loc1["lat"], loc1["lng"], loc2["lat"], loc2["lng"])
                    if distanza_km > 3.5:
                        continue # Evita di calcolare budget, orari e routing per posti lontanissimi

                # Budget Condiviso
                costo_totale = loc1["costo_medio"] + loc2["costo_medio"]
                
                if budget_max and costo_totale > budget_max:
                    continue
                    
                # Timeline Concatenata (il secondo locale deve essere aperto quando finisce il primo)
                if not self._is_locale_aperto(loc2.get("orari_google", []), stanza.data, ora_in_t2, "Nessun limite"):
                    continue
                    
                # SUPER-ENTITÀ: Uniamo i due nodi in uno per far felice il Frontend
                combo = {
                    "nome": f"{loc1['nome']} ➔ {loc2['nome']}",
                    "tipo": f"{loc1['tipo'].capitalize()} e {loc2['tipo'].capitalize()}",
                    "zona": f"Inizio: {loc1['zona'].split(',')[0]} | Poi: {loc2['zona'].split(',')[0]}",
                    "costo_medio": costo_totale,
                    "minuti_di_guida": 0 
                }
                combo["_zona_per_routing"] = loc1["zona"] # Calcoliamo il percorso casa -> locale 1
                combinazioni_valide.append(combo)
                
            locali_finali = combinazioni_valide
            if not locali_finali:
                messaggio_compromesso = "😭 I vincoli combinati (Budget Condiviso + Orari Sequenziali) sono troppo stringenti."

        # 5. BOUNDARY ROUTING (Calcolo Distanze)
        for locale in locali_finali:
            zona_dest = locale.get("_zona_per_routing", locale["zona"])
            tempi = []
            for p in partecipanti:
                if p.zona_partenza:
                    minuti = self.routing_client.calcola_tempo_percorso(p.zona_partenza, zona_dest, stanza.citta)
                    tempi.append(minuti)
            locale["minuti_di_guida"] = max(tempi) if tempi else 0

        # Ordinamento (ottimizza il tempo massimo di guida del gruppo)
        locali_finali.sort(key=lambda x: x.get("minuti_di_guida", 999))

        return {
            "vincoli_gruppo": {
                "orario_comune": orari_comuni,
                "budget_cap": budget_max,
                "restrizioni": restrizioni,
                "desideri_soddisfatti": termini_soddisfatti, 
                "piovera": pioverà,
                "vincoli_rilassati": vincoli_rilassati
            },
            "locali_proposti": locali_finali,
            "esito": messaggio_compromesso
        }

    def _is_locale_aperto(self, orari_google: list, data_uscita: str, ora_inizio: str, ora_fine: str) -> bool:
        if not orari_google:
            return True 

        try:
            if isinstance(data_uscita, (datetime, date)):
                data_obj = data_uscita
            else:
                data_obj = datetime.strptime(str(data_uscita).split(" ")[0], "%Y-%m-%d")

            giorno_google = (data_obj.weekday() + 1) % 7
            
            h_in, m_in = map(int, ora_inizio.split(":"))
            target_start = h_in * 60 + m_in
            if isinstance(ora_fine, str) and ":" in ora_fine:
                h_out, m_out = map(int, ora_fine.split(":"))
                target_end = h_out * 60 + m_out
                if target_end <= target_start:
                    target_end += 24 * 60
            else:
                target_end = target_start + 120
                
        except Exception as e:
            print(f"Errore parsing orari, salto filtro: {e}")
            return True

        for periodo in orari_google:
            apertura = periodo.get("open", {})
            chiusura = periodo.get("close", {})
            
            if apertura.get("day") == giorno_google:
                open_min = apertura.get("hour", 0) * 60 + apertura.get("minute", 0)
                
                if not chiusura:
                    return True
                    
                close_min = chiusura.get("hour", 0) * 60 + chiusura.get("minute", 0)
                
                if close_min <= open_min:
                    close_min += 24 * 60 
                
                if target_start >= open_min and target_end <= close_min:
                    return True
                    
        return False

    def _calcola_distanza_haversine(self, lat1, lon1, lat2, lon2) -> float:
        """Calcola la distanza in linea d'aria in KM tra due coordinate terrestri."""
        R = 6371.0 # Raggio della Terra in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c