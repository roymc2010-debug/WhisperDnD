"""Only synthetic saved inputs; recovery must never call transcription."""
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from src.api import server

@pytest.fixture
def saved(tmp_path,monkeypatch):
    monkeypatch.setenv('WHISPER_OUTPUT_DIR',str(tmp_path/'output'))
    monkeypatch.setenv('WHISPER_CAMPAIGNS_DIR',str(tmp_path/'campaigns'))
    folder=server.get_data_output_dir()/'generation-inputs';folder.mkdir(parents=True,exist_ok=True)
    rid='a'*32
    payload={'campaign_name':'Mesa','session_number':6,'raw_transcript':'Nora abre el cofre.','prepared_transcript':'Nora abre el cofre.','roster':[], 'context':{},'target_language':'es','source_recordings':[{'filename':'partida.wav','recorded_at':'2026-11-08T20:00:00','part_index':1}]}
    (folder/(rid+'.json')).write_text(json.dumps(payload),encoding='utf8')
    (folder/(rid+'-attempts.json')).write_text(json.dumps([{'attempt':1,'status':'failed','error_type':'ReadTimeout','seconds':600,'model':'chosen-model'}]),encoding='utf8')
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('','offline'))
    transcriber=MagicMock(side_effect=AssertionError('Recovery must not transcribe'))
    monkeypatch.setattr(server,'transcribe_audio_pipeline',transcriber)
    return TestClient(server.app),rid,folder,transcriber

def test_saved_failed_transcript_can_be_listed_without_exposing_its_contents(saved):
    client,rid,folder,transcriber=saved
    response=client.get('/api/generation-inputs')
    assert response.status_code==200
    row=response.json()[0]
    assert row['id']==rid and row['session_number']==6 and row['can_retry']
    assert 'raw_transcript' not in row and 'context' not in row

def test_retry_reuses_saved_text_and_is_idempotent_after_creating_a_draft(saved,monkeypatch):
    client,rid,folder,transcriber=saved
    process=MagicMock(return_value={'session_chapter':{'review_id':'b'*32},'session_number':6})
    monkeypatch.setattr(server,'process_session_for_campaign',process)
    response=client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True})
    assert response.status_code==200
    assert response.json()['review_id']=='b'*32
    assert process.call_args.kwargs['transcript_text']=='Nora abre el cofre.'
    assert process.call_args.kwargs['session_number']==6
    assert process.call_args.kwargs['custom_date']=='2026-11-08T20:00:00'
    assert process.call_args.kwargs['source_recordings'][0]['filename']=='partida.wav'
    assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True}).status_code==200
    assert process.call_count==1
    transcriber.assert_not_called()

def test_saved_response_is_reused_without_another_model_call(saved,monkeypatch):
    client,rid,folder,transcriber=saved
    (folder/(rid+'-response.json')).write_text(json.dumps({'session_chapter':{'title':'Recuperada','chronicle_text':'Nora abrió el cofre.'}}),encoding='utf8')
    process=MagicMock(return_value={'session_chapter':{'review_id':'c'*32}})
    monkeypatch.setattr(server,'process_session_for_campaign',process)
    response=client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True})
    assert response.status_code==200
    assert process.call_args.kwargs['cached_session_data']['session_chapter']['title']=='Recuperada'
    assert process.call_args.kwargs['cached_session_data']['session_chapter']['generation_metadata']['reused_response'] is True
    transcriber.assert_not_called()

def test_retry_requires_explicit_user_action(saved):
    client,rid,folder,transcriber=saved
    assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':False}).status_code==422
    assert client.post('/api/generation-inputs/not-an-id/retry',json={'confirm_generation':True}).status_code==404


def test_transcript_download_uses_saved_text_only(saved):
    client,rid,folder,transcriber=saved
    result=client.get('/api/generation-inputs/'+rid+'/transcript')
    assert result.status_code==200
    assert result.text=='Nora abre el cofre.'
    assert 'attachment' in result.headers['content-disposition']
    assert client.get('/api/generation-inputs/bad-id/transcript').status_code==404
    transcriber.assert_not_called()


def test_failed_retry_preserves_original_and_can_be_retried_explicitly(saved,monkeypatch):
    client,rid,folder,transcriber=saved
    original=(folder/(rid+'.json')).read_bytes()
    process=MagicMock(side_effect=RuntimeError('503 UNAVAILABLE'))
    monkeypatch.setattr(server,'process_session_for_campaign',process)
    assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True}).status_code==500
    assert (folder/(rid+'.json')).read_bytes()==original
    assert client.get('/api/generation-inputs').json()[0]['can_retry']
    transcriber.assert_not_called()


def test_retry_recovers_response_from_previous_recovery_attempt(saved,monkeypatch):
    client,rid,folder,transcriber=saved
    child='d'*32
    source=json.loads((folder/(rid+'.json')).read_text(encoding='utf8'))
    source['retry_of']=rid
    (folder/(child+'.json')).write_text(json.dumps(source),encoding='utf8')
    (folder/(child+'-response.json')).write_text(json.dumps({'session_chapter':{'title':'Guardada después del reintento','chronicle_text':'Nora abrió el cofre.'}}),encoding='utf8')
    process=MagicMock(return_value={'session_chapter':{'review_id':'e'*32}})
    monkeypatch.setattr(server,'process_session_for_campaign',process)
    assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True}).status_code==200
    assert process.call_args.kwargs['cached_session_data'] is not None
    assert len(client.get('/api/generation-inputs').json())==0


def test_recovery_does_not_start_a_second_call_while_child_outcome_is_unknown(saved):
    client,rid,folder,transcriber=saved
    child='d'*32
    source=json.loads((folder/(rid+'.json')).read_text(encoding='utf8'))
    source['retry_of']=rid
    (folder/(child+'.json')).write_text(json.dumps(source),encoding='utf8')
    assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True}).status_code==409


def test_concurrent_recovery_of_same_input_is_blocked(saved):
    from src.storage.generation_recovery import retry_input, GenerationRecoveryConflict
    client,rid,folder,transcriber=saved
    def process(*args):
        with pytest.raises(GenerationRecoveryConflict):
            retry_input(folder.parent,rid,lambda *args:pytest.fail('Duplicate generation'))
        return {'session_chapter':{'review_id':'f'*32}}
    assert retry_input(folder.parent,rid,process)['review_id']=='f'*32


def test_cached_response_stages_review_without_calling_gemini_or_changing_campaign(saved,monkeypatch):
    client,rid,folder,transcriber=saved
    manager=server.CampaignManager()
    manager.record_session('Mesa',{'title':'Anterior','chronicle_text':'Nora espera.'},session_number=5)
    before={str(p):p.read_bytes() for p in manager.campaigns_dir.rglob('*.json')}
    generate=MagicMock(side_effect=AssertionError('Cached recovery must not call Gemini'))
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',generate)
    (folder/(rid+'-response.json')).write_text(json.dumps({'session_chapter':{'title':'Recuperada','chronicle_text':'Nora abrió el cofre.'}}),encoding='utf8')
    result=client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True})
    assert result.status_code==200,result.text
    review=client.get('/api/session-reviews/'+result.json()['review_id']).json()
    assert review['transcript']=='Nora abre el cofre.'
    assert review['session_number']==6
    assert review['chapter']['date']=='08/11/2026'
    assert review['chapter']['source_recordings'][0]['recorded_at']=='2026-11-08T20:00:00'
    assert {str(p):p.read_bytes() for p in manager.campaigns_dir.rglob('*.json')}==before
    assert client.get('/api/generation-inputs').json()==[]
    generate.assert_not_called()
    transcriber.assert_not_called()


def test_original_pipeline_with_saved_response_is_not_offered_for_duplicate_recovery(saved):
    from src.storage.generation_recovery import active_input
    client,rid,folder,transcriber=saved
    (folder/(rid+'-response.json')).write_text('{}',encoding='utf8')
    with active_input(rid):
        assert client.get('/api/generation-inputs').json()[0]['can_retry'] is False
        assert client.post('/api/generation-inputs/'+rid+'/retry',json={'confirm_generation':True}).status_code==409


def test_recovery_status_reports_current_phase_without_source_contents(saved):
    from src.summarizer.generation_diagnostics import GenerationDiagnostics
    client,rid,folder,transcriber=saved
    trace=GenerationDiagnostics(folder/(rid+'-diagnostics.json'),'chosen-model')
    trace.record('waiting_response',attempt=1)
    response=client.get('/api/generation-inputs/'+rid+'/status')
    assert response.status_code==200
    data=response.json()
    assert data['generation']['phase']=='waiting_response'
    assert data['generation']['phase_elapsed_seconds']>=0
    assert 'Nora' not in response.text and 'raw_transcript' not in response.text
