"""Provider boundaries are synthetic; diagnostics must never retain content or keys."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest
from src.summarizer.gemini_client import GeminiTTRPGSummarizer


@pytest.mark.parametrize('failure,kind,status',[
    (SimpleNamespace(code=503),'GeminiUnavailable',503),
    (SimpleNamespace(code=504),'GeminiProviderTimeout',504),
    (httpx.ReadTimeout('SECRET-SOURCE'), 'GeminiTimeout',504),
    (httpx.ConnectError('SECRET-KEY'), 'GeminiConnectionError',502),
    (httpx.WriteTimeout('SECRET-SOURCE'), 'GeminiSendTimeout',504),
    (httpx.ConnectTimeout('SECRET-KEY'), 'GeminiConnectTimeout',504),
])
def test_failures_distinguish_provider_responses_from_transport(failure,kind,status):
    from src.summarizer.generation_diagnostics import classify_failure
    result=classify_failure(failure)
    assert result['kind']==kind
    assert result['http_status']==status
    assert 'SECRET' not in json.dumps(result)


def test_provider_failure_reaches_api_with_specific_safe_message(monkeypatch):
    from src.api import server
    class Unavailable(RuntimeError):code=503
    monkeypatch.setattr('src.summarizer.gemini_client.time.sleep',lambda seconds:None)
    s=GeminiTTRPGSummarizer(api_key='SECRET-KEY',model_name='chosen-model')
    s._client=SimpleNamespace(models=SimpleNamespace(generate_content=MagicMock(side_effect=Unavailable('SECRET-SOURCE SECRET-KEY'))))
    with pytest.raises(RuntimeError) as caught:s._generate_with_retry('SECRET-SOURCE')
    with pytest.raises(server.HTTPException) as response:server.raise_session_processing_error(caught.value,'specific-provider-error')
    assert response.value.status_code==503
    assert server.task_progress_state['specific-provider-error']['error_type']=='GeminiUnavailable'
    assert '503' in response.value.detail and 'SECRET' not in response.value.detail


def test_timestamps_advance_only_while_waiting_and_survive_stage_updates(monkeypatch):
    from src.api import server
    clock=[1000.0]
    monkeypatch.setattr(server.time,'time',lambda:clock[0])
    server.update_task_progress('timed-generation',65,'Esperando respuesta de Gemini',stage='analyzing',
        generation={'phase':'waiting_response','started_at':990.0,'phase_started_at':1000.0,'finished_at':None,'attempt':1})
    clock[0]=1200.0
    data=server.get_task_progress('timed-generation')
    assert data['generation']['phase_elapsed_seconds']==200
    assert data['generation']['elapsed_seconds']==210
    assert data['percent']==65
    server.set_task_error('timed-generation','Espera agotada',error_type='GeminiTimeout')
    clock[0]=1500.0
    data=server.get_task_progress('timed-generation')
    assert data['generation']['phase_elapsed_seconds']==200
    assert data['generation']['elapsed_seconds']==210


def test_real_sdk_transport_records_safe_stages_and_response(tmp_path,monkeypatch):
    from src.summarizer.generation_diagnostics import GenerationDiagnostics
    from google.genai import _api_client
    events=[]
    def provider(request):
        trace=request.extensions['trace']
        for event in ('connection.connect_tcp.started','connection.connect_tcp.complete','connection.start_tls.started','connection.start_tls.complete','http11.send_request_headers.started','http11.send_request_body.complete','http11.receive_response_headers.started'):
            trace(event,{})
        return httpx.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'text':'{"estado":"ok"}'}]},'finishReason':'STOP'}],
          'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':6,'totalTokenCount':16}})
    monkeypatch.setattr(_api_client,'SyncHttpxClient',lambda **kw:httpx.Client(transport=httpx.MockTransport(provider),**kw))
    path=tmp_path/'diagnostics.json'
    s=GeminiTTRPGSummarizer(api_key='SECRET-KEY',model_name='chosen-model')
    s.diagnostics=GenerationDiagnostics(path,'chosen-model',on_event=events.append)
    try:
        assert json.loads(s._generate_with_retry('SECRET-SOURCE'))=={'estado':'ok'}
    finally:s.client.close()
    data=json.loads(path.read_text(encoding='utf8'))
    assert 'SECRET' not in json.dumps(data)
    phases=[e['phase'] for e in data['events']]
    assert phases.index('sending_request') < phases.index('waiting_response') < phases.index('receiving_response')
    assert any(e.get('http_status')==200 for e in data['events'])
    assert events[-1]['phase']=='response_received'


def test_trace_write_failure_does_not_repeat_a_successful_provider_call(tmp_path,monkeypatch):
    from src.summarizer.generation_diagnostics import GenerationDiagnostics
    bad=tmp_path/'directory';bad.mkdir()
    s=GeminiTTRPGSummarizer(api_key='offline')
    s.diagnostics=GenerationDiagnostics(bad,'chosen-model')
    calls=[]
    def provider(**kw):calls.append(kw);return SimpleNamespace(text='{"estado":"ok"}',usage_metadata=None)
    s._client=SimpleNamespace(models=SimpleNamespace(generate_content=provider))
    assert s._generate_with_retry('synthetic')=='{"estado":"ok"}'
    assert len(calls)==1


def test_pipeline_saves_stage_trace_without_canon_or_sensitive_text(tmp_path,monkeypatch):
    from src.api import server
    monkeypatch.setenv('WHISPER_CAMPAIGNS_DIR',str(tmp_path/'campaigns'))
    monkeypatch.setenv('WHISPER_OUTPUT_DIR',str(tmp_path/'output'))
    manager=server.CampaignManager()
    manager.record_session('Mesa',{'title':'Anterior','chronicle_text':'Nora espera.'},session_number=5)
    before=manager.get_campaign_path('Mesa').read_bytes()
    def generate(instance,**kwargs):
        instance.diagnostics.record('waiting_response')
        progress=server.get_task_progress('traced-session')
        assert progress['generation']['phase']=='waiting_response'
        assert progress['percent']==65
        return {'session_chapter':{'title':'Prueba','chronicle_text':'Nora abrió el cofre.'}}
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',generate)
    result=server.process_session_for_campaign('Mesa','Nora abre el cofre.',session_number=6,gemini_api_key='SECRET-KEY',task_id='traced-session')
    folder=tmp_path/'output/generation-inputs'
    files=list(folder.glob('*-diagnostics.json'))
    assert len(files)==1
    data=json.loads(files[0].read_text(encoding='utf8'))
    assert data['phase']=='completed'
    assert 'saving_draft' in [e['phase'] for e in data['events']]
    assert 'Nora' not in json.dumps(data) and 'SECRET' not in json.dumps(data)
    assert manager.get_campaign_path('Mesa').read_bytes()==before
    assert result['session_chapter']['review_status']=='pending'


def test_provider_error_payload_preserves_failure_type(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api import server
    from src.summarizer.gemini_client import GeminiGenerationFailure
    class Unavailable(RuntimeError):code=503
    def fail(*args,**kwargs):raise GeminiGenerationFailure('chosen-model',Unavailable('SECRET-SOURCE'))
    monkeypatch.setattr(server,'process_session_for_campaign',fail)
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('', 'offline'))
    response=TestClient(server.app).post('/api/campaign/reprocess',json={'campaign_name':'Mesa','session_number':6,'transcript_text':'Nora abre el cofre.'})
    assert response.status_code==503
    assert response.json()['error_type']=='GeminiUnavailable'
    assert response.json()['stage']=='Comunicación con Gemini'
    assert 'SECRET' not in response.text


def test_durable_trace_distinguishes_failure_without_storing_exception_text(tmp_path):
    from src.summarizer.generation_diagnostics import GenerationDiagnostics
    from src.summarizer.gemini_client import GeminiGenerationFailure
    path=tmp_path/'trace.json'
    trace=GenerationDiagnostics(path,'chosen-model')
    with pytest.raises(GeminiGenerationFailure):
        with trace.pipeline():
            trace.record('waiting_response')
            raise GeminiGenerationFailure('chosen-model',httpx.ReadTimeout('SECRET-KEY SECRET-SOURCE'))
    data=json.loads(path.read_text(encoding='utf8'))
    assert data['failure_kind']=='GeminiTimeout'
    assert data['finished_at']>=data['started_at']
    assert 'SECRET' not in json.dumps(data)


def test_regenerate_endpoint_publishes_current_generation_phase(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from src.api import server
    monkeypatch.setenv('WHISPER_CAMPAIGNS_DIR',str(tmp_path/'campaigns'))
    monkeypatch.setenv('WHISPER_OUTPUT_DIR',str(tmp_path/'output'))
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('','offline'))
    def generate(instance,**kwargs):
        instance.diagnostics.record('waiting_response')
        assert server.get_task_progress('regenerate-trace')['generation']['phase']=='waiting_response'
        return {'session_chapter':{'title':'Prueba','chronicle_text':'Nora abrió el cofre.'}}
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',generate)
    response=TestClient(server.app).post('/api/campaign/reprocess',json={'campaign_name':'Mesa','session_number':6,'transcript_text':'Nora abre el cofre.','task_id':'regenerate-trace'})
    assert response.status_code==200,response.text
    assert server.get_task_progress('regenerate-trace')['generation']['finished_at']
