"""Progress reflects completed work, never elapsed-time guesses. Providers are fake."""
from unittest.mock import Mock
import pytest
from src.api import server
from src.transcription.groq_whisper import GroqWhisperTranscriber


def test_audio_slicing_cannot_jump_ahead_of_completed_transcription(tmp_path,monkeypatch):
    transcriber=GroqWhisperTranscriber(api_key='offline')
    chunks=[(str(tmp_path/('chunk'+str(i)+'.mp3')),i*60,60) for i in range(3)]
    def slicing(path,chunk_minutes,on_progress):
        on_progress(25,'Segmentación completada')
        return chunks
    monkeypatch.setattr(transcriber,'_slice_audio',slicing)
    monkeypatch.setattr(transcriber,'_transcribe_single_file',lambda *a,**kw:{'text':'Fuente','segments':[],'duration':60})
    monkeypatch.setattr('src.transcription.groq_whisper.clean_groq_chunks',lambda chunks:None)
    events=[]
    transcriber._transcribe_chunked(str(tmp_path/'audio.wav'),on_progress=lambda pct,msg:events.append(pct),min_pct=5,max_pct=55)
    assert events[0]==5
    assert events==sorted(events)
    assert events[-1]==55
    assert 21.7 in events


def test_local_transcription_uses_same_completion_range_as_cloud(tmp_path,monkeypatch):
    audio=tmp_path/'audio.mp3';audio.write_bytes(b'synthetic')
    monkeypatch.setattr(server,'_inspect_audio_duration_seconds',lambda path:240)
    monkeypatch.setattr(server,'build_whisper_prompt',lambda **kwargs:'')
    monkeypatch.setattr(server,'create_transcription_test_report',lambda **kwargs:tmp_path/'report.txt')
    def transcribe(*a,on_progress=None,**kw):
        for pct in (30,35,54.5,74):on_progress(pct,'Avance de audio')
        return {'text':'Fuente','segments':[],'duration':240,'language_code':'es'}
    monkeypatch.setattr(server,'LocalWhisperTranscriber',lambda **kw:Mock(transcribe=transcribe))
    events=[]
    server.transcribe_audio_pipeline(str(audio),engine='local',on_progress=lambda pct,msg:events.append(pct))
    assert events[-1]==55
    assert events==sorted(events)
    assert max(events)==55
