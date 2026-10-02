import pytest
from unittest.mock import AsyncMock, patch
from llm.extractor import extract_user_profile

@pytest.mark.anyio
@patch("llm.extractor.client.chat.completions.create", new_callable=AsyncMock)
async def test_extract_user_profile_success(mock_groq_create):
    
    mock_json_response = '''
    {
        "multi_tappa": false, 
        "budget_totale": 25.0, 
        "tappa_1": {"tipo_locale": "pizzeria", "preferenze": ["tranquillo"]}, 
        "richiesta_chiarimento": null
    }
    '''
    mock_groq_create.return_value.choices[0].message.content = mock_json_response
    
    risultato = await extract_user_profile("Voglio mangiare una pizza spendendo massimo 25 euro")
    
    assert risultato.status == "success"
    assert risultato.profile.budget_totale == 25.0
    assert risultato.profile.tappa_1.tipo_locale == "pizzeria"
    assert mock_groq_create.call_count == 2

# Impostiamo esplicitamente asyncio come unico backend per evitare che cerchi trio
@pytest.fixture
def anyio_backend():
    return "asyncio"