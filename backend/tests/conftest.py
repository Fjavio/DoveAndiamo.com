import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Il solver importa il mediatore LLM (Groq), che richiede la chiave API.
# Nei test lo sostituiamo con una versione finta che lascia le preferenze invariate.
async def _mediazione_finta(preferenze, tipo_locale, citta):
    return preferenze

_finto = types.ModuleType("llm.extractor")
_finto.mediate_preferences = _mediazione_finta
sys.modules["llm.extractor"] = _finto
