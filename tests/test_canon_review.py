"""Generated text and proposals must not become campaign facts before user review."""
import copy
import json
import pytest
from fastapi.testclient import TestClient
from src.api import server
from src.storage.campaign_manager import CampaignManager

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_CAMPAIGNS_DIR',str(tmp_path/'campaigns'))
    monkeypatch.setenv('WHISPER_OUTPUT_DIR',str(tmp_path/'output'))
    manager=CampaignManager()
    manager.record_session('Mesa',{'title':'Original','chronicle_text':'El huevo sigue con Nora.'},session_number=4,
                           updated_npcs=[{'name':'Nora','notes':['Cuida el huevo.']}])
    fake={'session_chapter':{'title':'Nueva','chronicle_text':'El huevo nace en diez días.','recap_text':'El huevo tiene un plazo.'},
          'updated_npcs':[{'name':'Nora','notes':['Nace en diez días.']}],
          'updated_quests':[{'id':'q1','title':'Volver antes de diez días','status':'in_progress'}],
          'items':[{'name':'Varita','holder':'Lia','status':'en_posesion'}],
          'detected_party':[], 'detected_pcs':[], 'locations':[], 'detected_npc_names':['Nora']}
    calls=[]
    def generate(*a,**kw): calls.append(kw); return copy.deepcopy(fake)
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',generate)
    return manager,TestClient(server.app),calls

def generate():
    return server.process_session_for_campaign('Mesa','[00:01:00] El viaje de ida y vuelta toma diez días. Lia identifica la varita.',session_number=4,gemini_api_key='offline')

def test_generation_stages_draft_without_replacing_existing_session_or_canon(setup):
    manager,client,calls=setup
    before={str(p):p.read_bytes() for p in manager.campaigns_dir.rglob('*.json')}
    result=generate()
    assert result['session_chapter'].get('review_id'), 'Generation must return a reviewable draft'
    assert {str(p):p.read_bytes() for p in manager.campaigns_dir.rglob('*.json')}==before
    assert result['processing_warnings']
    review=client.get('/api/session-reviews/'+result['session_chapter']['review_id']).json()
    assert review['status']=='pending'
    assert len(review['proposals'])==3
    assert all(not p['evidence']['verified'] for p in review['proposals'])
    assert 'identifica' in review['transcript']

def test_review_can_reject_all_proposals_and_save_corrected_text_without_gemini(setup):
    manager,client,calls=setup
    result=generate();rid=result['session_chapter'].get('review_id')
    assert rid, 'Missing review draft'
    draft=client.get('/api/session-reviews/'+rid).json()
    payload={'revision':draft['revision'],'selected':[], 'chapter':{'chronicle_text':'Nora acepta cuidar el huevo. El plazo no se conoce.','recap_text':'El huevo queda a salvo.'}}
    response=client.post('/api/session-reviews/'+rid+'/apply',json=payload)
    assert response.status_code==200
    saved=manager.load_modular('Mesa')
    assert len(saved['sessions'])==1
    assert saved['sessions'][0]['chronicle_text']==payload['chapter']['chronicle_text']
    assert not any('diez' in json.dumps(n,ensure_ascii=False) for n in saved['npcs'])
    assert not saved.get('items')
    assert saved['sessions'][0]['raw_transcript'].startswith('[00:01:00]')
    assert len(calls)==1
    assert client.post('/api/session-reviews/'+rid+'/apply',json=payload).status_code==200
    assert len(manager.load_modular('Mesa')['sessions'])==1

def test_campaign_changes_after_draft_require_new_review_without_overwriting(setup):
    manager,client,calls=setup
    result=generate();rid=result['session_chapter'].get('review_id')
    assert rid
    draft=client.get('/api/session-reviews/'+rid).json()
    manager.update_wiki_entity('Mesa','npc','Nora',{'description':'Corrección manual reciente'})
    before=manager.get_campaign_path('Mesa').read_bytes()
    response=client.post('/api/session-reviews/'+rid+'/apply',json={'revision':draft['revision'],'selected':[],'chapter':{}})
    assert response.status_code==409
    assert manager.get_campaign_path('Mesa').read_bytes()==before

def test_only_selected_proposals_are_committed(setup):
    manager,client,calls=setup
    result=generate();rid=result['session_chapter'].get('review_id')
    assert rid
    draft=client.get('/api/session-reviews/'+rid).json()
    item=next(p for p in draft['proposals'] if p['collection']=='items')
    response=client.post('/api/session-reviews/'+rid+'/apply',json={'revision':draft['revision'],'selected':[item['id']],'chapter':{'chronicle_text':'Texto revisado.'}})
    assert response.status_code==200
    assert manager.load_modular('Mesa')['items'][0]['name']=='Varita'
    assert not manager.load_modular('Mesa').get('quests')


def test_review_does_not_fuzzy_merge_similar_npc_names(setup,monkeypatch):
    manager,client,calls=setup
    manager.record_session('Mesa',{'title':'Antes'},session_number=3,updated_npcs=[{'name':'Nora','notes':['Identidad anterior.']}])
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',lambda *a,**kw:{'session_chapter':{'title':'Otra','chronicle_text':'Llegó Nora del Mar.'},'updated_npcs':[{'name':'Nora del Mar','notes':['Otra persona.']}]})
    result=generate();rid=result['session_chapter']['review_id'];draft=client.get('/api/session-reviews/'+rid).json()
    response=client.post('/api/session-reviews/'+rid+'/apply',json={'revision':draft['revision'],'selected':['npcs:0'],'chapter':{}})
    assert response.status_code==200
    assert {n['name'] for n in manager.load_modular('Mesa')['npcs']}=={'Nora','Nora del Mar'}


def test_changed_campaign_can_refresh_comparison_without_new_generation(setup):
    manager,client,calls=setup
    result=generate();rid=result['session_chapter']['review_id'];draft=client.get('/api/session-reviews/'+rid).json()
    manager.update_wiki_entity('Mesa','npc','Nora',{'description':'Corrección confirmada'})
    response=client.post('/api/session-reviews/'+rid+'/refresh',json={'revision':draft['revision'],'chapter':{'chronicle_text':'Mi texto revisado.'}})
    assert response.status_code==200
    new=client.get('/api/session-reviews/'+response.json()['id']).json()
    assert new['proposals'][0]['before']['description']=='Corrección confirmada'
    assert new['chapter']['chronicle_text']=='Mi texto revisado.'
    assert len(calls)==1
    accepted=client.post('/api/session-reviews/'+new['id']+'/apply',json={'revision':new['revision'],'selected':[],'chapter':{}})
    assert accepted.status_code==200
    assert manager.load_modular('Mesa')['npcs'][0]['description']=='Corrección confirmada'
    assert client.post('/api/session-reviews/'+rid+'/apply',json={'revision':draft['revision'],'selected':[],'chapter':{}}).status_code==409


def test_literal_quote_is_not_automatic_permission_to_update_canon(setup,monkeypatch):
    manager,client,calls=setup
    quote='El viaje de ida y vuelta toma diez días.'
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',lambda *a,**kw:{'session_chapter':{'title':'Huevos','chronicle_text':'El huevo nace en diez días.'},'updated_npcs':[{'name':'Nora','notes':['El huevo nace en diez días.']}],'evidence':[{'collection':'npcs','key':'Nora','quotes':[quote]}]})
    before=manager.get_campaign_path('Mesa').read_bytes()
    result=generate();draft=client.get('/api/session-reviews/'+result['session_chapter']['review_id']).json()
    assert draft['proposals'][0]['evidence']['verified'] is True
    assert manager.get_campaign_path('Mesa').read_bytes()==before


def test_draft_downloads_are_available_without_committing(setup):
    manager,client,calls=setup
    result=generate();rid=result['session_chapter']['review_id']
    assert client.get('/api/session-reviews/'+rid+'/download').status_code==200
    assert client.get('/api/record/download-md',params={'filename':rid+'.md'}).status_code==200
    response=client.get('/api/download/transcript/'+rid+'_transcripcion.txt')
    assert response.status_code==200
    assert 'identifica' in response.text
    assert client.get('/api/session-reviews/not-a-review').status_code==404


def test_failed_generation_keeps_reusable_input_without_touching_campaign(setup,monkeypatch):
    manager,client,calls=setup
    def fail(*a,**kw):raise RuntimeError('503 simulated')
    monkeypatch.setattr(server.GeminiTTRPGSummarizer,'generate_campaign_session',fail)
    before=manager.get_campaign_path('Mesa').read_bytes()
    with pytest.raises(RuntimeError):generate()
    inputs=list((server.get_data_output_dir()/'generation-inputs').glob('*.json'))
    saved=[json.loads(p.read_text(encoding='utf8')) for p in inputs if not p.name.endswith('-attempts.json')]
    assert any('identifica' in item.get('raw_transcript','') for item in saved)
    assert manager.get_campaign_path('Mesa').read_bytes()==before


def test_review_audit_metadata_does_not_count_as_a_session_event():
    from src.storage.session_mutations import _references
    session={'chronicle_text':'El grupo descansó.', 'canon_evidence':{'selected':[{'before':{'name':'Sombra Antigua'}}]}}
    assert not _references(session,{'name':'Sombra Antigua'})
