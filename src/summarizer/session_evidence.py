"""Conservative, offline checks before spending tokens or updating campaign canon."""
import re
import unicodedata


class InsufficientSessionContent(ValueError):
    """The transcript is empty or consists entirely of social pleasantries."""


def prepare_session_transcript(text, roster=None):
    from src.transcription.groq_whisper import clean_whisper_hallucinations

    cleaned = clean_whisper_hallucinations((text or "").strip(), roster=roster)
    speech = []
    for line in cleaned.splitlines():
        # Strip metadata only for classification; preserve the actual transcript.
        line = re.sub(r"\[Fragmento \d+: audio no reconocido\]", "", line)
        line = re.sub(r"^\s*\[\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
                      r"(?:\s*(?:--?>|–|-)\s*\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?\]\s*", "", line)
        line = re.sub(r"^\s*\[[^\]\n]+\]\s*:\s*", "", line)
        line = re.sub(r"^\s*\[(?:silence|silencio|noise|ruido|music|música)\]\s*$", "", line, flags=re.I)
        speech.append(line)
    normalized = unicodedata.normalize("NFKD", " ".join(speech).casefold())
    normalized = " ".join(re.findall(r"[^\W_]+", "".join(c for c in normalized if not unicodedata.combining(c))))
    pleasantry = (r"(?:hola|hello|hi|hey|buenas|buenos dias|buenas tardes|buenas noches|"
                  r"adios|hasta luego|hasta pronto|hasta manana|hasta la proxima|nos vemos|"
                  r"bye|goodbye|see ya|see you later|see you|gracias|thank you|thanks|"
                  r"ok|okay|vale|bueno|chau|chao|ciao)")
    if not normalized or re.fullmatch(rf"{pleasantry}(?: {pleasantry})*", normalized):
        raise InsufficientSessionContent(
            "La transcripción está vacía o solo contiene saludos o despedidas. "
            "No hay contenido suficiente para generar una crónica ni actualizar la campaña. "
            "El audio original se conserva.")
    return cleaned
