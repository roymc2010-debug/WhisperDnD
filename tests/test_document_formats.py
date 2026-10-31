"""Contracts for the two Work & Study output formats; provider calls are stubbed."""
import asyncio
import inspect
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from src.api import server
from src.api.routers import academic
from src.summarizer.gemini_client import GeminiTTRPGSummarizer

TRANSCRIPT = 'Ana revisará el diseño el viernes. Se acordó publicar después de revisarlo.'
MEETING_MD = '# Resumen de reunión: Diseño\n\n## 1. Resumen\nRevisión del diseño.\n\n## 2. Decisiones y acuerdos\n- Publicar después de la revisión.\n\n## 3. Tareas y responsables\n- Revisar el diseño — Responsable: Ana — Fecha: viernes.\n'

@pytest.fixture
def isolated(monkeypatch,tmp_path):
    for key in ('WHISPER_INPUT_DIR','WHISPER_OUTPUT_DIR','WHISPER_CAMPAIGNS_DIR'):
        directory=tmp_path/key
        directory.mkdir()
        monkeypatch.setenv(key,str(directory))
    monkeypatch.setenv('TESTING','1')
    monkeypatch.setenv('WHISPER_ENV','test')
    monkeypatch.setattr(server,'validate_api_keys_or_raise',lambda *a,**kw:None)
    monkeypatch.setattr(server,'extract_client_api_keys',lambda request:('test','test'))
    monkeypatch.setattr(server,'trigger_drive_sync_background',lambda *a,**kw:None)
    generated=Mock(return_value=MEETING_MD)
    summarizer=Mock(generate_academic_notes=generated)
    monkeypatch.setattr(server,'GeminiTTRPGSummarizer',lambda **kw:summarizer)
    pipeline_signature=inspect.signature(server.transcribe_audio_pipeline)
    def transcribe(*args,**kwargs):
        pipeline_signature.bind(*args,**kwargs)
        return {'text':TRANSCRIPT,'formatted_transcript':TRANSCRIPT,'segments':[],'language':'es','duration':2.0}
    monkeypatch.setattr(server,'transcribe_audio_pipeline',transcribe)
    wav=server.get_data_input_dir()/'sample.wav'
    wav.write_bytes(b'RIFF'+b'\x00'*60)
    monkeypatch.setattr(server,'download_youtube_audio',lambda *a,**kw:str(wav))
    monkeypatch.setattr(server,'active_recorder',Mock(is_recording=True,mode='class',_file_path=str(wav),stop=Mock(return_value=str(wav))))
    return generated

@pytest.mark.parametrize('endpoint,payload',[
 ('/api/transcribe/youtube',{'url':'https://www.youtube.com/watch?v=test','workspace':'work_and_study'}),
 ('/api/record/stop-and-process',{}),
 ('/api/summarize/switch-language',{'transcript_text':TRANSCRIPT,'target_language':'en'}),
 ('/api/campaign/reprocess',{'transcript_text':TRANSCRIPT,'workspace':'work_and_study'}),
])
def test_format_reaches_generation_and_response(endpoint,payload,isolated):
    payload={**payload,'recording_mode':'class','subject':'Diseño','topic':'Entrega','document_format':'executive'}
    with TestClient(server.app) as client:
        response=client.post(endpoint,json=payload)
    assert response.status_code==200,response.text
    assert isolated.call_args.kwargs['document_format']=='executive'
    assert response.json()['document_format']=='executive'

@pytest.mark.parametrize('endpoint,field',[
 ('/api/transcribe/file','file'),('/api/sessions/upload-with-telemetry','file'),
])
def test_uploaded_format_reaches_generation(endpoint,field,isolated):
    with TestClient(server.app) as client:
        response=client.post(endpoint,data={'recording_mode':'class','subject':'Diseño','topic':'Entrega','document_format':'executive'},files={field:('test.wav',b'RIFF'+b'\x00'*60,'audio/wav')})
    assert response.status_code==200,response.text
    assert isolated.call_args.kwargs['document_format']=='executive'
    assert response.json()['document_format']=='executive'

def test_invalid_document_format_is_rejected(isolated):
    with TestClient(server.app) as client:
        response=client.post('/api/campaign/reprocess',json={'transcript_text':TRANSCRIPT,'recording_mode':'class','document_format':'anything'})
    assert response.status_code==422
    isolated.assert_not_called()

def test_meeting_generation_uses_meeting_instructions_and_keeps_meeting_sections():
    summarizer=GeminiTTRPGSummarizer.__new__(GeminiTTRPGSummarizer)
    summarizer.model_name='gemini-2.5-flash'
    provider=Mock(return_value=MEETING_MD)
    summarizer._generate_with_retry=provider
    result=summarizer.generate_academic_notes(TRANSCRIPT,subject='Diseño',topic='Entrega',document_format='executive')
    prompt=provider.call_args.args[0]
    assert 'Decisiones y acuerdos' in prompt
    assert 'Tareas y responsables' in prompt
    assert TRANSCRIPT in prompt
    assert '## 3. Tareas y responsables' in result
    assert 'Glosario Conceptual' not in result

def test_meeting_tasks_and_decisions_are_not_turned_into_a_glossary():
    tasks,decisions=server.extract_academic_sections(MEETING_MD,document_format='executive')
    assert tasks==['Revisar el diseño — Responsable: Ana — Fecha: viernes.']
    assert 'Publicar después de la revisión.' in decisions
    assert 'Glosario' not in decisions

def test_short_meeting_survives_library_and_consolidation(isolated):
    filename='apuntes_reunion_equipo_20261031_100000.md'
    (server.get_data_output_dir()/filename).write_text(MEETING_MD,encoding='utf-8')
    before=asyncio.run(academic.list_academic_notes())["notes"]
    assert any(n["filename"]==filename for n in before)
    academic.update_consolidated_academic_notes_file()
    notes=asyncio.run(academic.list_academic_notes())['notes']
    assert any(n['filename']==filename for n in notes)


def test_meeting_word_export_uses_meeting_labels(tmp_path):
    from docx import Document
    from src.exporters.docx_exporter import export_academic_notes_docx
    target=tmp_path/'meeting.docx'
    export_academic_notes_docx(MEETING_MD,subject='Diseño',topic='Entrega',output_path=str(target),document_format='executive')
    text='\n'.join(p.text for p in Document(target).paragraphs)
    assert 'Resumen de reunión' in text
    assert 'Guía de Estudio Universitaria' not in text
    assert 'Apuntes de Clase' not in text
