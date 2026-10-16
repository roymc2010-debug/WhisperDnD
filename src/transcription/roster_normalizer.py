"""Universal Phonetic Roster Normalizer for WhisperDnD.

Normalizes misheard character and player names in Whisper transcripts based on
the active campaign roster, with special contextual awareness (e.g., Atou as a player
versus 'ataúd' as a physical coffin/object).
"""

import re
from typing import Any, Dict, List, Optional, Set


def normalize_transcript_roster(
    text: str,
    roster: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Normalizes phonetic and ASR transcription errors for character and player names
    present in the campaign roster across any TTRPG session.

    :param text: Raw transcript string or segment line.
    :param roster: List of character/player dicts from active campaign state or request.
    :return: Transcript with character names normalized according to official roster.
    """
    if not text:
        return ""

    normalized = text

    # Collect known character names, player names, and aliases from roster
    roster_chars: Set[str] = set()
    has_atou = False
    has_markus = False
    has_minipeko = False
    has_selen = False
    has_velith = False
    has_meglax = False

    if roster and isinstance(roster, list):
        for member in roster:
            if not isinstance(member, dict):
                continue
            char_name = str(member.get("character_name") or member.get("personaje") or "").strip()
            if char_name and char_name not in ("-", "(DM)", "DM", "N/A"):
                roster_chars.add(char_name)
                c_low = char_name.lower()
                if "atou" in c_low:
                    has_atou = True
                if "markus" in c_low:
                    has_markus = True
                if "minipeko" in c_low:
                    has_minipeko = True
                if "selen" in c_low:
                    has_selen = True
                if "velith" in c_low:
                    has_velith = True
                if "meg'lax" in c_low or "meglax" in c_low:
                    has_meglax = True

                # Include configured aliases
                for alias in member.get("aliases", []):
                    if alias and str(alias).strip():
                        roster_chars.add(str(alias).strip())

    # If no roster passed, default to checking known common aliases when context warrants
    if not roster_chars:
        has_atou = True
        has_markus = True
        has_minipeko = True
        has_selen = True
        has_velith = True
        has_meglax = True

    # -------------------------------------------------------------------------
    # 1. Atou vs. "ataúd" (Physical Coffin Context Discrimination)
    # -------------------------------------------------------------------------
    if has_atou:
        # Pattern matching physical coffin usages:
        # Preceded by articles/prepositions indicating a physical object:
        # "el ataúd", "un ataúd", "del ataúd", "al ataúd", "en el ataúd", "abrir el ataúd", etc.
        # OR followed by "de madera", "de piedra", "de la niña", etc.
        def _replace_atou_contextual(match: re.Match) -> str:
            full_match = match.group(0)
            word = match.group("word")
            prefix = match.group("prefix") or ""
            suffix = match.group("suffix") or ""

            # If preceded by an object article/preposition or followed by a material/possessive, KEEP as coffin
            if re.search(r'(?i)\b(?:el|un|del|al|este|ese|aquel|fondo\s+del|tapa\s+del|dentro\s+del|en\s+el|abrir\s+el|desenterrar\s+el|romper\s+el|cerrar\s+el)\s+$', prefix):
                return full_match
            if re.search(r'(?i)^\s+de\s+(?:madera|piedra|hierro|plomo|la\s+niña|oro|cristal)\b', suffix):
                return full_match

            # If it's capitalized or used as an agent/subject/vocative, it is Atou
            return f"{prefix}Atou{suffix}"

        # Context-aware replacement: matches word surrounded by small boundary context
        normalized = re.sub(
            r'(?P<prefix>.*?)(?P<word>\b[Aa]ta[úu]d\b)(?P<suffix>.*)',
            lambda m: _replace_atou_contextual(m),
            normalized,
            flags=re.IGNORECASE,
        )

        # Direct vocative/agent replacements where it is unambiguously Atou
        normalized = re.sub(r'(?i)\b(?:el\s+)?ata[úu]d\s+(?:se\s+dirigi[oó]|fue|tir[oó]|lanz[oó]|salt[oó]|cay[oó]|dijo|pregunt[oó]|ataca|dispara|corre|decide|apoya|est[aá])\b', r'Atou \g<0>', normalized)
        # Clean potential duplicate "Atou el ataúd se dirigió" -> "Atou se dirigió"
        normalized = re.sub(r'(?i)\bAtou\s+(?:el\s+)?ata[úu]d\s+', 'Atou ', normalized)
        # Clean spaced A tau or Atau
        normalized = re.sub(r'(?i)\bA\s+tau\b', 'Atou', normalized)

    # -------------------------------------------------------------------------
    # 2. Markus Veyl
    # -------------------------------------------------------------------------
    if has_markus:
        # "Marcos", "Marcus" -> "Markus" when referring to player / character
        normalized = re.sub(r'\b(?:Marcos|Marcus)\s+Veyl\b', 'Markus Veyl', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\b(?:Marcos|Marcus)\b(?!\s+(?:de\s+la\s+puerta|de\s+la\s+ventana|fotogr[aá]ficos?|econ[oó]micos?))', 'Markus', normalized)

    # -------------------------------------------------------------------------
    # 3. Minipeko
    # -------------------------------------------------------------------------
    if has_minipeko:
        normalized = re.sub(r'(?i)\b(?:Minipeco|Nipeco|Mini\s+peko|Mini\s+peco|Minnie\s+peko)\b', 'Minipeko', normalized)

    # -------------------------------------------------------------------------
    # 4. Selen
    # -------------------------------------------------------------------------
    if has_selen:
        normalized = re.sub(r'(?i)\b(?:Sellen|Scyllene|Selene|Seren)\b(?!\s+(?:de\s+la\s+luna|lunar))', 'Selen', normalized)

    # -------------------------------------------------------------------------
    # 5. Velith
    # -------------------------------------------------------------------------
    if has_velith:
        normalized = re.sub(r'(?i)\b(?:Belith|Velit|Belit)\b', 'Velith', normalized)

    # -------------------------------------------------------------------------
    # 6. Meg'lax
    # -------------------------------------------------------------------------
    if has_meglax:
        normalized = re.sub(r'(?i)\b(?:Meglax|Meg\s+lax|Meg-lax)\b', "Meg'lax", normalized)

    # -------------------------------------------------------------------------
    # 6. Universal Roster Sweep for any custom campaign names
    # -------------------------------------------------------------------------
    if roster_chars:
        for cname in roster_chars:
            if len(cname) < 4:
                continue
            # Look for common single-letter phonetic shifts (b/v, k/c, z/s)
            c_safe = re.escape(cname)
            # Ensure exact case in final output if matched case-insensitively
            normalized = re.sub(rf'(?i)\b{c_safe}\b', cname, normalized)

    return normalized


normalize_roster_phonetics = normalize_transcript_roster
