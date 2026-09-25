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

Devi estrarre i seguenti campi:
- "budget_max": numero decimale o intero indicante la spesa massima in euro (es. 25.0). Null se non specificato.
- "disponibile_da": orario "HH:MM" (es. "18:30"). Null se non specificato.
- "disponibile_a": orario "HH:MM" limite per il rientro (es. "23:30"). Null se non specificato.
- "restrizioni_alimentari": lista di stringhe con vincoli alimentari (es. ["vegetariano", "celiaco"]). Lista vuota se non presenti.
- "mezzo_trasporto": stringa indicante il mezzo (es. "auto", "metro", "mezzi pubblici", "piedi"). Null se non specificato.
- "mezzi_esclusi": lista di mezzi che l'utente NON vuole prendere (es. ["piedi", "autobus"]).
- "zona_partenza": indirizzo o quartiere esatto da cui parte l'utente. Null se non specificato.
- "importanza_distanza": stringa tra "bassa", "media", "alta". Deducila se l'utente esprime quanto è disposto a spostarsi (es. "non voglio allontanarmi" -> "alta"). Null se non deducibile.
- "preferenze_aggiuntive": lista di stringhe che cattura qualsiasi desiderio extra sull'atmosfera, il tipo di serata, i servizi o un idea di dove andare (es. ["posto romantico", "musica dal vivo", "economico", "tranquillo", "all'aperto", "zona sud-est è bella"]). Lista vuota se non presenti.
- "richiesta_chiarimento": stringa con una domanda cortese da porre all'utente. 

REGOLE CRITICHE:
1. CONTRADDIZIONI LOGICHE: Se il messaggio contiene palesi contraddizioni irrisolvibili (es. "sono vegano ma voglio una braceria") o richieste del tutto incomprensibili, usa "richiesta_chiarimento" per chiedere educatamente di risolvere il conflitto.
2. LUOGHI INCOMPRENSIBILI: Se l'utente indica un luogo generico o informale (es. "sto da nonna", "a casa mia"), lascia "zona_partenza": null e scrivi una breve domanda in "richiesta_chiarimento" chiedendo di specificare la zona o il quartiere.
3. LE OMISSIONI NON SONO ERRORI: Se un dato (es. zona di partenza, budget, orari) è semplicemente omesso o non menzionato, NON chiedere MAI chiarimenti. Lascia il campo null. L'utente non è obbligato a specificare tutto.
4. DESTINAZIONE VS PARTENZA: Distingui la "zona_partenza" dalla destinazione desiderata. Se l'utente suggerisce DOVE vuole andare (es. "propongo una zona fuori dal centro"), salvalo in "preferenze_aggiuntive" e NON chiedere chiarimenti sulla zona di partenza se omette da dove parte. Se la zona di partenza è chiara o assente (non menzionata affatto), "richiesta_chiarimento" DEVE essere null.
5. Fai estrema attenzione alle negazioni (es. "non sono celiaco", "basta che non sia pesce" -> restrizioni, "no auto" -> mezzi_esclusi).
"""

SYSTEM_PROMPT_REFLECTION = """
Sei un validatore logico di background per un sistema AI (Pattern Self-Reflection).
Confronta il messaggio originale dell'utente con il JSON estratto.
Verifica in particolare:
1. Coerenza delle negazioni (es. l'utente ha detto "NON vegetariano" ma nel JSON è finito "vegetariano"? Correggi).
2. Interpretazione corretta del budget massimo.
3. Se "zona_partenza" non è un quartiere reale o è troppo vago, assicurati che sia null e che "richiesta_chiarimento" contenga la domanda per l'utente.
4. Assicurati che nessuna sfumatura o richiesta extra (es. "voglio stare all'aperto", "posto tranquillo") sia stata persa; inseriscile nella lista "preferenze_aggiuntive".

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