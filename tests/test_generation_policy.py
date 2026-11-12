import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from src.summarizer.gemini_client import GeminiTTRPGSummarizer


def test_transient_errors_stay_on_selected_model_and_do_not_sleep_after_last(monkeypatch):
    s=GeminiTTRPGSummarizer(api_key='offline',model_name='chosen-model')
    s._client=SimpleNamespace(models=SimpleNamespace(generate_content=MagicMock(side_effect=RuntimeError('503 UNAVAILABLE'))))
    waits=[];monkeypatch.setattr('src.summarizer.gemini_client.time.sleep',waits.append)
    with pytest.raises(RuntimeError):s._generate_with_retry('synthetic')
    assert len(s._client.models.generate_content.call_args_list)==3
    assert {c.kwargs['model'] for c in s._client.models.generate_content.call_args_list}=={'chosen-model'}
    assert len(waits)==2


def test_generation_has_request_timeout_and_metadata_without_prompt_contents(monkeypatch):
    s=GeminiTTRPGSummarizer(api_key='offline',model_name='chosen-model')
    response=SimpleNamespace(text='ok',usage_metadata=SimpleNamespace(total_token_count=31,prompt_token_count=20,candidates_token_count=7,thoughts_token_count=4))
    fn=MagicMock(return_value=response);s._client=SimpleNamespace(models=SimpleNamespace(generate_content=fn))
    assert s._generate_with_retry('PRIVATE SOURCE')=='ok'
    assert fn.call_args.kwargs['config']['http_options']['timeout']>0
    from google.genai.types import GenerateContentConfig
    assert GenerateContentConfig(**fn.call_args.kwargs['config']).http_options.timeout>0
    assert s._generation_attempts[0]['model']=='chosen-model'
    assert s._generation_attempts[0]['tokens']['thoughts']==4
    assert 'PRIVATE SOURCE' not in json.dumps(s._generation_attempts)


def test_evidence_survives_parser_for_review():
    raw={'session_chapter':{'chronicle_text':'Texto.'},'evidence':[{'collection':'items','key':'Varita','quotes':['Lia identifica la varita.']} ]}
    result=GeminiTTRPGSummarizer.parse_json_response(json.dumps(raw),1)
    assert result.get('evidence')==raw['evidence']


def test_total_budget_prevents_starting_another_request(monkeypatch):
    clock=[0.0]
    monkeypatch.setenv('GEMINI_GENERATION_TIMEOUT_SECONDS','10')
    monkeypatch.setattr('src.summarizer.gemini_client.time.monotonic',lambda:clock[0])
    def fail(**kw):clock[0]=11;raise RuntimeError('503 UNAVAILABLE')
    fn=MagicMock(side_effect=fail);s=GeminiTTRPGSummarizer(api_key='offline');s._client=SimpleNamespace(models=SimpleNamespace(generate_content=fn))
    with pytest.raises(RuntimeError):s._generate_with_retry('synthetic')
    assert fn.call_count==1


def test_provider_retry_after_is_honored(monkeypatch):
    class Busy(RuntimeError):response=SimpleNamespace(headers={'Retry-After':'8'})
    fn=MagicMock(side_effect=Busy('429 RESOURCE_EXHAUSTED'));s=GeminiTTRPGSummarizer(api_key='offline');s._client=SimpleNamespace(models=SimpleNamespace(generate_content=fn))
    waits=[];monkeypatch.setattr('src.summarizer.gemini_client.time.sleep',waits.append)
    with pytest.raises(RuntimeError):s._generate_with_retry('synthetic')
    assert waits==[8,8]


def test_read_timeout_is_reported_as_timeout_without_blind_regeneration(monkeypatch):
    import httpx
    from src.api import server
    fn=MagicMock(side_effect=httpx.ReadTimeout('Read operation timed out'))
    s=GeminiTTRPGSummarizer(api_key='offline',model_name='chosen-model');s._client=SimpleNamespace(models=SimpleNamespace(generate_content=fn))
    with pytest.raises(RuntimeError) as caught:s._generate_with_retry('synthetic')
    assert 'tiempo de espera' in str(caught.value).lower()
    assert 'chosen-model' in str(caught.value)
    assert fn.call_count==1
    with pytest.raises(server.HTTPException) as response:server.raise_session_processing_error(caught.value,'timeout-test')
    assert response.value.status_code==504
    assert server.task_progress_state['timeout-test']['error_type']=='GeminiTimeout'


def test_prompt_repeats_neither_language_nor_json_rules_and_keeps_source():
    from src.summarizer.prompts import build_continuity_session_prompt
    source='Nora negocia el pasaje y conserva el recibo.'
    prompt=build_continuity_session_prompt('Mesa',[],[],source,6,target_language='en')
    assert prompt.count('CRITICAL LANGUAGE DIRECTIVE')==1
    assert prompt.count('CRITICAL JSON SYNTAX RULE')==1
    assert prompt.count(source)==1
    assert 'CHRONICLE AND COVERAGE CONTRACT' in prompt
