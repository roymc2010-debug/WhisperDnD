"""Offline contracts for detailed chronicles without campaign-specific prompt bias.

These inspect the prompt delivered to the client; they do not claim to measure
literary quality or factual fidelity of a live model response.
"""
import json
import re

import pytest

from src.summarizer.gemini_client import GeminiTTRPGSummarizer
from src.summarizer.prompts import build_continuity_session_prompt


def prompt_for(language="es", **kwargs):
    return build_continuity_session_prompt(
        roster_formatted="Jugadora: Ana | Personaje: Arin | Clase: Mago",
        existing_quests=[], known_npcs=[],
        transcript_text="Arin abre la puerta. El custodio pide que protejan la llave.",
        session_number=4, target_language=language, **kwargs,
    )


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("youtube", [False, True])
def test_chronicle_has_coverage_contract_separate_from_brief_recap(language, youtube):
    prompt = prompt_for(language, is_youtube=youtube)
    expected = {
        "es": ["CONTRATO DE CRÓNICA Y COBERTURA", "prosa narrativa desarrollada",
               "no es el recap", "decisiones, pistas y consecuencias", "comprueba la cobertura"],
        "en": ["CHRONICLE AND COVERAGE CONTRACT", "developed narrative prose",
               "is not the recap", "decisions, clues and consequences", "check coverage"],
    }
    for instruction in expected[language]:
        assert instruction in prompt
    field = re.search(r'"chronicle_text": "([^\n]+)"', prompt)[1]
    assert ("escenas desarrolladas" if language == "es" else "developed scenes") in field
    assert ("sin mínimo" if language == "es" else "no minimum") in prompt


@pytest.mark.parametrize("language", ["es", "en"])
def test_prompt_has_no_fixed_campaign_roster_or_adventure_spelling_dictionary(language):
    prompt = prompt_for(language)
    for foreign in ("Minipeko", "Selen", "Atou", "Markus Veyl", "Sir Yato", "Aquilus Bunker",
                    "Halendiel Fang", "Liam O'Brien", "Brantifax", "Halsey", "Bundru", "Octus"):
        assert foreign not in prompt, f"Unrelated campaign identity leaked into the {language} prompt: {foreign}"
    assert "Arin" in prompt


@pytest.mark.parametrize("language", ["es", "en"])
def test_real_campaign_names_are_preserved_when_supplied_as_evidence(language):
    prompt = build_continuity_session_prompt(
        roster_formatted="Personaje jugador: Minipeko; mago kenku",
        existing_quests=[], known_npcs=[{"name": "Naxxolosis", "role": "Custodio", "notes": []}],
        transcript_text="Minipeko pregunta a Naxxolosis cómo proteger el huevo.",
        session_number=4, target_language=language,
    )
    assert "Personaje jugador: Minipeko; mago kenku" in prompt
    assert "Naxxolosis (Custodio" in prompt
    assert "Minipeko pregunta a Naxxolosis cómo proteger el huevo." in prompt
    assert "Minipeko)" not in prompt  # No companion/pet example is appended.


@pytest.mark.parametrize("language", ["es", "en"])
def test_loot_ownership_is_never_assigned_by_default(language):
    prompt = prompt_for(language)
    if language == "es":
        assert "por defecto al INVENTARIO GENERAL DEL GRUPO" not in prompt
        assert "propiedad o custodia no confirmada" in prompt
    else:
        assert "defaults strictly to the GROUP/PARTY INVENTORY" not in prompt
        assert "ownership or custody unconfirmed" in prompt


@pytest.mark.parametrize("language", ["es", "en"])
def test_uncertain_labels_and_whisper_artifacts_are_not_canon_or_personal_criticism(language):
    prompt = prompt_for(language, user_character={"character_name": "Arin", "player_name": "Ana"})
    clauses = {
        "es": ["etiquetas de hablante no prueban", "errores de reconocimiento",
               "no demuestran una oportunidad desaprovechada", "Sugerencias opcionales",
               "no declares una acción individual como colectiva"],
        "en": ["speaker labels do not prove", "recognition errors",
               "do not establish a missed opportunity", "Optional suggestions",
               "do not turn an individual action into a collective one"],
    }
    for clause in clauses[language]:
        assert clause in prompt
    assert "OBLIGATORIO — detecta" not in prompt
    assert "MANDATORY — detect" not in prompt


@pytest.mark.parametrize("language", ["es", "en"])
def test_real_client_receives_full_source_and_does_not_shorten_chronicle(monkeypatch, language):
    transcript = (
        "[00:00:01 -> 00:00:04] [Arin]: Abro la puerta.\n"
        "[00:10:04 -> 00:10:08] [Custodio]: La mina está cerrada; no sabemos la causa.\n"
        "[00:20:00 -> 00:20:04] [Arin]: Acepto investigar, pero la llave se queda aquí."
    )
    chronicle = "### Escena 1\n" + "El custodio explica el cierre de la mina. " * 100
    response = {"session_chapter": {"title": "La puerta", "chronicle_text": chronicle,
                                    "recap_text": "Visitaron al custodio."}}
    calls = []
    def fake_generate(self, contents, config=None):
        calls.append((contents, config))
        return json.dumps(response)
    monkeypatch.setattr(GeminiTTRPGSummarizer, "_generate_with_retry", fake_generate)
    result = GeminiTTRPGSummarizer(api_key="offline").generate_campaign_session(
        transcript, [], session_number=4, target_language=language)
    assert len(calls) == 1
    assert calls[0][1]["response_mime_type"] == "application/json"
    assert "La mina está cerrada; no sabemos la causa." in calls[0][0]
    assert "Abro la puerta." in calls[0][0]
    assert "Acepto investigar, pero la llave se queda aquí." in calls[0][0]
    assert ("CONTRATO DE CRÓNICA Y COBERTURA" if language == "es" else "CHRONICLE AND COVERAGE CONTRACT") in calls[0][0]
    assert result["session_chapter"]["chronicle_text"] == chronicle
    assert result["session_chapter"]["recap_text"] != chronicle
