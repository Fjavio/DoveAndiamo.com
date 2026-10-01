import os
import json
from groq import AsyncGroq
from models.schemas import ExtractedProfile, LLMResponse

# Inizializzazione del client asincrono Groq
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL = "qwen/qwen3.8-27b"

SYSTEM_PROMPT_EXTRACTION = """
Sei il motore di Natural Language Understanding di "Jammo", un sistema che organizza uscite di gruppo.
Il tuo compito è estrarre le preferenze e i vincoli espressi da un utente in linguaggio naturale e restituire ESCLUSIVAMENTE un oggetto JSON valido.

NUOVA STRUTTURA MULTI-TAPPA E BUDGET:
- "multi_tappa": booleano. Imposta a true SOLO se l'utente chiede chiaramente due fasi distinte (es. "aperitivo e poi cena", "pizza e pub dopo", "cena e poi andiamo a bere").
- "budget_totale": numero (es. 40.0). Compilalo se l'utente dà una cifra unica per tutta la serata.
- "tappa_1": oggetto che rappresenta il primo evento (es. la cena). Contiene "tipo_locale" (es. "pizzeria"), "budget" (solo se assegna un budget specifico per questa fase) e "preferenze" (lista di desideri sull'atmosfera per questa fase, es. ["romantico"]). Valorizzalo sempre.
- "tappa_2": oggetto che rappresenta il secondo evento. Stessa struttura di tappa_1. Valorizzalo SOLO se multi_tappa è true.

VINCOLI GLOBALI DELLA SERATA:
- "disponibile_da" e "disponibile_a": orari "HH:MM" (es. "18:30" e "23:30"). Null se non specificati.
- "restrizioni_alimentari": lista (es. ["vegetariano", "celiaco"]). Lista vuota se non presenti.
- "mezzo_trasporto": (es. "auto", "metro", "piedi"). Null se non specificato.
- "mezzi_esclusi": lista di mezzi sgraditi (es. ["piedi", "autobus"]).
- "zona_partenza": quartiere esatto. Null se non specificato.
- "importanza_distanza": tra "bassa", "media", "alta". Null se non deducibile.
- "richiesta_chiarimento": domanda cortese da porre all'utente in caso di input confuso.

REGOLE CRITICHE:
1. SEPARAZIONE DELLE ATMOSFERE: Se l'utente scrive "cena in posto tranquillo, e poi pub con musica a palla", DEVI separare. In tappa_1.preferenze metterai ["tranquillo"], in tappa_2.preferenze metterai ["musica a palla", "vivace"]. NON mischiare mai le atmosfere di due tappe diverse.
2. CONTRADDIZIONI LOGICHE: Usa "richiesta_chiarimento" se ci sono conflitti irrisolvibili.
3. LUOGHI INCOMPRENSIBILI: Se indica luoghi generici (es. "casa mia", "zona mia"), lascia "zona_partenza" null e chiedi in "richiesta_chiarimento" di specificare il quartiere.
4. LE OMISSIONI NON SONO ERRORI: Se manca un dato, lascialo null. Non chiedere MAI chiarimenti per dati omessi.
5. NEGAZIONI: Fai estrema attenzione a "non sono celiaco", "basta che non sia pesce" (-> restrizioni), "no auto" (-> mezzi_esclusi).
"""

SYSTEM_PROMPT_REFLECTION = """
Sei un validatore logico di background per un sistema AI (Pattern Self-Reflection).
Confronta il messaggio originale dell'utente con il JSON estratto.
Verifica in particolare:
1. Gestione Multi-Tappa: Se l'utente ha chiaramente richiesto due fasi (es. "cena e drink"), assicurati che multi_tappa sia true e che tappa_1 e tappa_2 siano compilate correttamente, senza mischiare le preferenze di un locale con quelle dell'altro.
2. Budget: Assicurati che un budget dichiarato per "tutta la serata" finisca in budget_totale e non in una singola tappa.
3. Coerenza delle negazioni (es. ha detto "NON vegetariano" ma nel JSON è finito "vegetariano"? Correggi).
4. Se "zona_partenza" non è reale, assicurati che sia null e che ci sia una "richiesta_chiarimento".

Restituisci ESCLUSIVAMENTE il JSON finale corretto, conforme allo schema richiesto.
"""

async def extract_user_profile(user_message: str) -> LLMResponse:
    """
    Estrae il profilo utente dal testo ed esegue una Self-Reflection per garantire RNF2.
    """
    # 1. Primo Passaggio: Estrazione Nominale (RF03)
    response_extraction = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION},
            {"role": "user", "content": user_message}
        ],
        temperature=0.0,  # Zero per garantire determinismo e stabilità (RNF8)
        response_format={"type": "json_object"}
    )
    
    raw_json_str = response_extraction.choices[0].message.content

    # 2. Secondo Passaggio: Self-Reflection in background (RNF2)
    reflection_payload = f"Messaggio originale: '{user_message}'\nJSON estratto: {raw_json_str}"
    
    response_reflection = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_REFLECTION},
            {"role": "user", "content": reflection_payload}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    validated_json = json.loads(response_reflection.choices[0].message.content)
    
    # Costruzione dell'oggetto validato da Pydantic
    profile = ExtractedProfile(**validated_json)

    # 3. Decisione di Business: Chiarimento (RF04) o Successo
    if profile.richiesta_chiarimento:
        return LLMResponse(
            status="clarification_needed",
            profile=profile,
            message_to_user=profile.richiesta_chiarimento
        )

    return LLMResponse(
        status="success",
        profile=profile,
        message_to_user="Preferenze acquisite con successo."
    )

async def generate_group_explanation(vincoli: dict, locali: list) -> str:
    """Trasforma i risultati del Solver in un messaggio chiaro all'utente"""
    
    if not locali:
        return "Purtroppo le vostre esigenze incrociate erano davvero troppo stringenti e non ho trovato locali compatibili. Proviamo ad allargare un po' i requisiti!"

    nomi_locali = ", ".join([l['nome'] for l in locali])
    desideri = ", ".join(vincoli.get('desideri_soddisfatti', []))
    
    # NOVITÀ: Controlliamo se il Solver ha rilassato i vincoli
    rilassati = vincoli.get('vincoli_rilassati', False)
    
    # Prepariamo un'istruzione aggiuntiva per il prompt se c'è stato compromesso
    istruzione_compromesso = ""
    if rilassati:
        istruzione_compromesso = "\n- NOTA PER L'IA: Per trovare questi locali è stato necessario sforare leggermente il budget minimo del gruppo (+20%). Menziona con molta leggerezza e simpatia che hai dovuto fare una piccolissima eccezione economica pur di salvare la serata e rispettare tutti i gusti, ma fallo sembrare un successo!"

    prompt = f"""
    Sei 'Jammo', un simpatico e caloroso organizzatore di uscite AI. Hai appena calcolato un itinerario.
    Dati elaborati dal tuo algoritmo interno:
    - Locali scelti: {nomi_locali}
    - Preferenze semantiche del gruppo considerate: {desideri if desideri else 'Uscita classica'}{istruzione_compromesso}
    
    Scrivi un allegro e breve messaggio (max 3 frasi) per il gruppo.
    Spiega con entusiasmo perché questi locali sono un ottimo compromesso per le loro atmosfere e gusti. 
    REGOLA CRITICA: NON rivelare MAI i vincoli specifici di una persona, non parlare mai di cifre esatte in euro, e non dire esplicitamente le intolleranze per rispettare la privacy. Sii un bravo organizzatore e focus sulla positività!
    """
    
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, # Alziamo un po' la creatività per questo task discorsivo
        )
        return response.choices[0].message.content
    except Exception:
        return "Ecco la proposta perfetta calcolata in base ai vostri vincoli incrociati!"