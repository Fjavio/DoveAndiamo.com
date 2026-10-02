"""Test del solver multi-tappa senza chiamare Google, Groq o Open-Meteo.

Avvio (dalla cartella backend):  py -m pytest
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

from core.solver import ItinerarySolver


class SolverDiProva(ItinerarySolver):
    """elabora_proposta è asincrona (chiama il mediatore LLM): nei test la eseguiamo direttamente."""
    def elabora_proposta(self, stanza, partecipanti):
        return asyncio.run(super().elabora_proposta(stanza, partecipanti))


def orari(apertura, chiusura):
    """Orari nel formato di Google Places, uguali per tutti i giorni."""
    return [{"open": {"day": d, "hour": apertura[0], "minute": apertura[1]},
             "close": {"day": d, "hour": chiusura[0], "minute": chiusura[1]}} for d in range(7)]


def locale(nome, tipo, costo, apertura=(19, 0), chiusura=(1, 0), all_aperto=False, lat=40.85, lng=14.25):
    return {"nome": nome, "tipo": tipo, "zona": f"Via {nome}, Napoli", "lat": lat, "lng": lng,
            "costo_medio": costo, "all_aperto": all_aperto, "orari_google": orari(apertura, chiusura)}


class FintoPlaces:
    def __init__(self, ristoranti, pub):
        self.ristoranti, self.pub = ristoranti, pub

    def cerca_locali_tappa(self, citta, tipo, preferenze, restrizioni, max_locali=20):
        scelti = self.pub if tipo in ("pub", "bar", "cocktail bar") else self.ristoranti
        return [dict(l) for l in scelti]


def crea_solver(ristoranti, pub=(), pioggia=False, minuti=15):
    s = SolverDiProva.__new__(SolverDiProva)      # niente chiavi API
    s.places_db = FintoPlaces(list(ristoranti), list(pub))
    s.weather_client = SimpleNamespace(check_rain=lambda citta, data: pioggia)
    s.routing_client = SimpleNamespace(calcola_tempo_percorso=lambda da, a, citta: minuti)
    return s


def persona(**campi):
    """Come la tabella Partecipante (che non ha budget_max)."""
    base = dict(disponibile_da=None, disponibile_a=None, zona_partenza="Vomero", restrizioni_alimentari=[],
                multi_tappa=False, budget_totale=None, tappa_1=None, tappa_2=None, mezzo_trasporto=None)
    base.update(campi)
    return SimpleNamespace(**base)


STANZA = SimpleNamespace(citta="Napoli", data=datetime(2026, 10, 9, 20, 0))
PIZZERIA = locale("Pizzeria", "pizzeria", 15)
PUB = locale("Pub", "pub", 15, apertura=(18, 0), chiusura=(3, 0))


def nomi(risultato):
    return [l["nome"] for l in risultato["locali_proposti"]]


def test_funziona_anche_se_nessuno_indica_il_budget():
    r = crea_solver([PIZZERIA]).elabora_proposta(STANZA, [persona(), persona()])
    assert nomi(r) == ["Pizzeria"]


def test_budget_minimo_del_gruppo():
    caro = locale("Caro", "ristorante", 60)
    r = crea_solver([PIZZERIA, caro]).elabora_proposta(STANZA, [persona(budget_totale=20), persona(budget_totale=80)])
    assert nomi(r) == ["Pizzeria"] and r["vincoli_gruppo"]["budget_cap"] == 20


def test_budget_dalle_singole_tappe():
    p = persona(tappa_1={"budget": 10}, tappa_2={"budget": 8})
    assert crea_solver([PIZZERIA])._calcola_budget_gruppo([p]) == 18


def test_sforamento_budget_massimo_20_per_cento():
    r = crea_solver([PIZZERIA]).elabora_proposta(STANZA, [persona(budget_totale=13)])
    assert nomi(r) == ["Pizzeria"] and r["vincoli_gruppo"]["vincoli_rilassati"]
    r = crea_solver([PIZZERIA]).elabora_proposta(STANZA, [persona(budget_totale=10)])
    assert nomi(r) == []


def test_rientro_dopo_mezzanotte():
    r = crea_solver([PIZZERIA]).elabora_proposta(
        STANZA, [persona(disponibile_da="20:00", disponibile_a="01:30")])
    assert r["vincoli_gruppo"]["orario_comune"] == {"da": "20:00", "a": "01:30"}
    assert nomi(r) == ["Pizzeria"]


def test_orari_senza_zero_iniziale():
    r = crea_solver([PIZZERIA]).elabora_proposta(
        STANZA, [persona(disponibile_da="9:30", disponibile_a="23:00"), persona(disponibile_da="21:00")])
    assert r["vincoli_gruppo"]["orario_comune"] == {"da": "21:00", "a": "23:00"}


def test_orari_incompatibili_nessuna_proposta():
    r = crea_solver([PIZZERIA]).elabora_proposta(
        STANZA, [persona(disponibile_a="20:00"), persona(disponibile_da="21:00")])
    assert nomi(r) == [] and r["vincoli_gruppo"]["orario_comune"] is None
    assert "orari" in r["esito"].lower()


def test_locale_chiuso_escluso():
    pranzo = locale("Solo pranzo", "ristorante", 15, apertura=(12, 0), chiusura=(15, 0))
    r = crea_solver([pranzo, PIZZERIA]).elabora_proposta(STANZA, [persona()])
    assert nomi(r) == ["Pizzeria"]


def test_pioggia_esclude_locali_all_aperto():
    chalet = locale("Chalet", "ristorante", 15, all_aperto=True)
    r = crea_solver([chalet, PIZZERIA], pioggia=True).elabora_proposta(STANZA, [persona()])
    assert nomi(r) == ["Pizzeria"] and r["vincoli_gruppo"]["piovera"]


def test_multi_tappa_cena_e_pub():
    r = crea_solver([PIZZERIA], [PUB]).elabora_proposta(STANZA, [persona(budget_totale=40, multi_tappa=True)])
    assert nomi(r) == ["Pizzeria ➔ Pub"] and r["locali_proposti"][0]["costo_medio"] == 30


def test_multi_tappa_pub_dopo_mezzanotte():
    r = crea_solver([PIZZERIA], [PUB]).elabora_proposta(
        STANZA, [persona(multi_tappa=True, disponibile_da="22:30")])
    assert nomi(r) == ["Pizzeria ➔ Pub"]


def test_multi_tappa_pub_gia_chiuso():
    presto = locale("Pub presto", "pub", 10, apertura=(18, 0), chiusura=(22, 0))
    r = crea_solver([PIZZERIA], [presto]).elabora_proposta(STANZA, [persona(multi_tappa=True)])
    assert nomi(r) == []


def test_multi_tappa_budget_condiviso_e_sforamento():
    r = crea_solver([PIZZERIA], [PUB]).elabora_proposta(STANZA, [persona(budget_totale=25, multi_tappa=True)])
    assert nomi(r) == ["Pizzeria ➔ Pub"] and r["vincoli_gruppo"]["vincoli_rilassati"]
    r = crea_solver([PIZZERIA], [PUB]).elabora_proposta(STANZA, [persona(budget_totale=20, multi_tappa=True)])
    assert nomi(r) == []


def test_multi_tappa_locali_troppo_lontani():
    lontano = locale("Pub lontano", "pub", 10, apertura=(18, 0), chiusura=(3, 0), lat=40.95, lng=14.25)
    r = crea_solver([PIZZERIA], [lontano]).elabora_proposta(STANZA, [persona(multi_tappa=True)])
    assert nomi(r) == []    # circa 11 km: oltre il limite di 10 km


def test_ordinamento_per_tempo_di_viaggio():
    s = crea_solver([locale("Lontano", "ristorante", 15), locale("Vicino", "ristorante", 15)])
    s.routing_client = SimpleNamespace(
        calcola_tempo_percorso=lambda da, a, citta: 40 if "Lontano" in a else 10)
    r = s.elabora_proposta(STANZA, [persona()])
    assert nomi(r) == ["Vicino", "Lontano"] and r["locali_proposti"][0]["minuti_di_guida"] == 10


def test_minuti_dopo_mezzanotte():
    assert ItinerarySolver._minuti("01:30") == 25 * 60 + 30
    assert ItinerarySolver._minuti("21:00") == 21 * 60
    assert ItinerarySolver._minuti("boh") is None


def test_multi_tappa_somma_il_tragitto_tra_i_due_locali():
    s = crea_solver([PIZZERIA], [PUB])
    s.routing_client = SimpleNamespace(
        calcola_tempo_percorso=lambda da, a, citta: 7 if da.startswith("Via Pizzeria") else 15)
    r = s.elabora_proposta(STANZA, [persona(multi_tappa=True)])
    assert r["locali_proposti"][0]["minuti_di_guida"] == 15 + 7   # casa -> cena + cena -> pub

def test_routing_in_parallelo():
    """Le chiamate a Google Directions partono insieme: 8 tratte da 0,3 s non devono richiedere 2,4 s."""
    import time
    ristoranti = [locale(f"R{i}", "ristorante", 15) for i in range(4)]

    def lento(da, a, citta):
        time.sleep(0.3)
        return 10

    s = crea_solver(ristoranti)
    s.routing_client = SimpleNamespace(calcola_tempo_percorso=lento)
    inizio = time.perf_counter()
    r = s.elabora_proposta(STANZA, [persona(zona_partenza="Vomero"), persona(zona_partenza="Chiaia")])
    durata = time.perf_counter() - inizio
    assert len(nomi(r)) == 4 and durata < 1.2     # in sequenza sarebbero 8 x 0,3 = 2,4 s