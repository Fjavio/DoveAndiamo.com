from datetime import datetime, date
from typing import List, Dict
import itertools
import asyncio
from external.places_db import PlacesDatabase
from external.weather_client import WeatherClient
from external.routing_client import RoutingClient
import math
from llm.extractor import mediate_preferences

class ItinerarySolver:
    """
    Classe Control (Pattern ECB) responsabile del calcolo dell'itinerario.
    Ora supporta il Prodotto Cartesiano per itinerari Multi-Tappa.
    """
    def __init__(self):
        self.places_db = PlacesDatabase()
        self.weather_client = WeatherClient()
        self.routing_client = RoutingClient()

    @staticmethod
    def _minuti(orario: str):
        """'HH:MM' -> minuti dalla mezzanotte. Gli orari prima delle 6:00 sono dopo mezzanotte (+24h)."""
        try:
            h, m = map(int, str(orario).strip().split(":")[:2])
        except (ValueError, AttributeError):
            return None
        minuti = h * 60 + m
        return minuti + 24 * 60 if h < 6 else minuti

    @staticmethod
    def _orario(minuti: int) -> str:
        return f"{(minuti // 60) % 24:02d}:{minuti % 60:02d}"

    def _calcola_intersezione_orari(self, stanza: any, partecipanti: List[any]) -> Dict[str, str]:
        orario_base = stanza.data.strftime("%H:%M")
        inizi = [self._minuti(p.disponibile_da) for p in partecipanti if p.disponibile_da]
        fini = [self._minuti(p.disponibile_a) for p in partecipanti if p.disponibile_a]
        inizi = [m for m in inizi if m is not None]
        fini = [m for m in fini if m is not None]

        if not inizi and not fini:
            return {"da": orario_base, "a": "Nessun limite"}
        max_start = max(inizi + [self._minuti(orario_base)])
        if not fini:
            return {"da": self._orario(max_start), "a": "Nessun limite"}
        min_end = min(fini)
        if max_start >= min_end:
            return None
        return {"da": self._orario(max_start), "a": self._orario(min_end)}

    def _calcola_budget_gruppo(self, partecipanti: List[any]) -> float:
        budget_min = 9999.0
        for p in partecipanti:
            # Sfruttiamo il nuovo campo budget_totale se esiste, altrimenti il fallback sul vecchio budget_max
            b = p.budget_totale or getattr(p, "budget_max", None)
            if not b:
                per_tappa = [t.get("budget") for t in (p.tappa_1, p.tappa_2) if t and t.get("budget")]
                b = sum(per_tappa) if per_tappa else None
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

    async def elabora_proposta(self, stanza: any, partecipanti: List[any]) -> Dict: #async perche stiamo chiamando un LLM asincrono
        # VINCOLI GLOBALI
        orari_comuni = self._calcola_intersezione_orari(stanza, partecipanti)
        budget_max = self._calcola_budget_gruppo(partecipanti)
        restrizioni = self._estrai_restrizioni_comuni(partecipanti)
        pioverà = self.weather_client.check_rain(stanza.citta, stanza.data)

        if orari_comuni is None:
            return {
                "vincoli_gruppo": {
                    "orario_comune": None, "budget_cap": budget_max, "restrizioni": restrizioni,
                    "desideri_soddisfatti": [], "piovera": pioverà, "vincoli_rilassati": False
                },
                "locali_proposti": [],
                "esito": "😭 Gli orari dei partecipanti non si sovrappongono: nessuna fascia oraria comune."
            }
        
        # RILEVAMENTO MODALITÀ (Singola vs Multi-Tappa)
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

        # L'INTERVENTO DEL MEDIATORE AI: Se ci sono desideri multipli, l'AI risolve i conflitti geografici e logici
        pref_t1_mediate = await mediate_preferences(list(pref_t1), tipo_t1, stanza.citta)
        pref_t2_mediate = await mediate_preferences(list(pref_t2), tipo_t2, stanza.citta) if is_multi else []

        # GENERAZIONE DEL POOL (Usando le preferenze mediate!)
        locali_t1 = self.places_db.cerca_locali_tappa(stanza.citta, tipo_t1, pref_t1_mediate, restrizioni)
        
        ora_in = orari_comuni.get("da", "20:00")
        locali_t1 = [l for l in locali_t1 if not (pioverà and l.get("all_aperto")) and self._is_locale_aperto(l.get("orari_google", []), stanza.data, str(ora_in), "Nessun limite")]
        
        locali_finali = []
        vincoli_rilassati = False
        messaggio_compromesso = "Calcolo completato nel rispetto di tutti i vincoli incrociati."
        termini_soddisfatti = list(pref_t1) + list(pref_t2)
        
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
            if not locali_finali:
                messaggio_compromesso = "😭 Nessun locale rispetta insieme budget, orari, meteo e restrizioni alimentari."
                    
        else:
            # LOGICA MULTI-TAPPA (ESPLOSIONE COMBINATORIA): ipotizziamo che per tappa_2 il filtro delle restrizioni alimentari non sia imprenscindibile
            locali_t2 = self.places_db.cerca_locali_tappa(stanza.citta, tipo_t2, pref_t2_mediate, [])
            locali_t2 = [l for l in locali_t2 if not (pioverà and l.get("all_aperto"))]
            
            combinazioni = list(itertools.product(locali_t1, locali_t2))
            
            # Calcolo dinamico della Timeline Concatenata (stimiamo 2 ore per la Tappa 1)
            ora_in_t2 = self._orario(self._minuti(ora_in) + 120)
            
            def combina(budget):
                combinazioni_valide = []
                for loc1, loc2 in combinazioni:
                    # Filtro Haversine: Scarta a priori i locali distanti più di tot km in linea d'aria
                    if loc1.get("lat") and loc2.get("lat"):
                        distanza_km = self._calcola_distanza_haversine(loc1["lat"], loc1["lng"], loc2["lat"], loc2["lng"])
                        if distanza_km > 10:
                            continue # Evita di calcolare budget, orari e routing per posti lontanissimi

                    # Budget Condiviso
                    costo_totale = loc1["costo_medio"] + loc2["costo_medio"]
                
                    if budget and costo_totale > budget:
                        continue
                    
                    # Timeline Concatenata (il secondo locale deve essere aperto quando finisce il primo)
                    if not self._is_locale_aperto(loc2.get("orari_google", []), stanza.data, ora_in_t2, "Nessun limite"):
                        continue
                    
                    # SUPER-ENTITÀ: Uniamo i due nodi in uno per il Frontend
                    combo = {
                        "nome": f"{loc1['nome']} ➔ {loc2['nome']}",
                        "tipo": f"{loc1['tipo'].capitalize()} e {loc2['tipo'].capitalize()}",
                        "zona": f"Inizio: {loc1['zona'].split(',')[0]} | Poi: {loc2['zona'].split(',')[0]}",
                        "costo_medio": costo_totale,
                        "minuti_di_guida": 0 
                    }
                    combo["_zona_per_routing"] = loc1["zona"] # Percorso casa -> locale 1
                    combo["_zona_tappa2"] = loc2["zona"]      # NUOVO: Memorizziamo l'indirizzo del locale 2
                    combinazioni_valide.append(combo)
                return combinazioni_valide

            locali_finali = combina(budget_max)
            if not locali_finali and budget_max:  # Graceful Degradation sul budget, come per la singola tappa
                locali_finali = combina(budget_max * 1.2)
                if locali_finali:
                    vincoli_rilassati = True
                    messaggio_compromesso = "⚠️ Applicato lieve compromesso economico sul budget."
            if not locali_finali:
                messaggio_compromesso = "😭 I vincoli combinati (Budget Condiviso + Orari Sequenziali) sono troppo stringenti."

        # BOUNDARY ROUTING (Calcolo Distanze Totali)
        tratte = set()
        for locale in locali_finali:
            zona_tappa1 = locale.get("_zona_per_routing", locale["zona"])
            if locale.get("_zona_tappa2"):
                tratte.add((zona_tappa1, locale["_zona_tappa2"]))
            for p in partecipanti:
                if p.zona_partenza:
                    tratte.add((p.zona_partenza, zona_tappa1))
        tratte = list(tratte)
        risultati = await asyncio.gather(*[
            asyncio.to_thread(self.routing_client.calcola_tempo_percorso, da, a, stanza.citta) for da, a in tratte
        ])
        tempi = dict(zip(tratte, risultati))

        for locale in locali_finali:
            zona_tappa1 = locale.get("_zona_per_routing", locale["zona"])
            zona_tappa2 = locale.get("_zona_tappa2") # Se esiste, è un itinerario multi-tappa
            
            # Calcoliamo il tempo di spostamento interno (Locale 1 ➔ Locale 2)
            tempo_interno = 0
            if zona_tappa2:
                tempo_interno = tempi[(zona_tappa1, zona_tappa2)]
            
            # Calcoliamo chi ci mette di più ad arrivare al Locale 1 da casa
            tempi_da_casa = []
            for p in partecipanti:
                if p.zona_partenza:
                    minuti_casa_t1 = tempi[(p.zona_partenza, zona_tappa1)]
                    tempi_da_casa.append(minuti_casa_t1)
            
            tempo_max_arrivo = max(tempi_da_casa) if tempi_da_casa else 0
            
            # Il tempo totale mostrato all'utente sarà la somma dei due viaggi
            locale["minuti_di_guida"] = tempo_max_arrivo + tempo_interno

        # Ordinamento (ottimizza il tempo massimo di guida totale del gruppo)
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
            
            target_start = self._minuti(ora_inizio)
            if isinstance(ora_fine, str) and ":" in ora_fine:
                target_end = self._minuti(ora_fine)
                if target_end <= target_start:
                    target_end += 24 * 60
            else:
                target_end = target_start + 120
            if target_start is None or target_end is None:
                return True
                
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