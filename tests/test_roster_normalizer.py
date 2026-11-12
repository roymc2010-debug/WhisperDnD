"""Unit tests for Roster Phonetic Normalizer and Anti-Hallucination rules."""

import unittest
from src.transcription.roster_normalizer import normalize_roster_phonetics
from src.transcription.groq_whisper import clean_whisper_hallucinations


class TestRosterNormalizer(unittest.TestCase):
    """Test suite for phonetic roster normalization and grammatical disambiguation."""

    def test_object_word_is_not_rewritten_into_a_character(self):
        """An animated object is possible fiction; grammar does not prove identity."""
        sample = "Atención, el Ataúd se dirigió hacia el centro de la ciudad."
        normalized = normalize_roster_phonetics(sample)
        self.assertEqual(normalized, sample)

    def test_atou_dialogue_normalized(self):
        sample = "A tau preguntó quién era el espectro."
        normalized = normalize_roster_phonetics(sample, [{"character_name": "Atou", "aliases": ["A tau"]}])
        self.assertIn("Atou preguntó", normalized)

    def test_physical_coffin_preserved(self):
        """When ataúd refers to a physical coffin object, preserve it."""
        sample1 = "Decidieron abrir el ataúd de la niña con una palanca."
        normalized1 = normalize_roster_phonetics(sample1)
        self.assertIn("abrir el ataúd", normalized1)

        sample2 = "Metieron el cuerpo dentro del ataúd de piedra."
        normalized2 = normalize_roster_phonetics(sample2)
        self.assertIn("dentro del ataúd", normalized2)

    def test_phonetic_variants_normalized(self):
        """Test common phonetic mishearings for Markus, Minipeko, Selen, Velith."""
        sample = "Marcos y Minipeco ayudaron a Sellen mientras Belith cantaba una balada."
        roster = [{"character_name": "Markus", "aliases": ["Marcos"]},
                  {"character_name": "Minipeko", "aliases": ["Minipeco"]},
                  {"character_name": "Selen", "aliases": ["Sellen"]},
                  {"character_name": "Velith", "aliases": ["Belith"]}]
        normalized = normalize_roster_phonetics(sample, roster)
        self.assertIn("Markus", normalized)
        self.assertIn("Minipeko", normalized)
        self.assertIn("Selen", normalized)
        self.assertIn("Velith", normalized)

    def test_clean_whisper_hallucinations_subtitle_prefixes(self):
        """Test removing single-letter subtitle prefixes like 'E. ', 'B. ', 'T. ', 'E.V.E.: '."""
        sample = "E. Yo creo que es el collar. B. Pero no sé por qué. T. ¿Y qué vio?"
        cleaned = clean_whisper_hallucinations(sample)
        self.assertEqual(cleaned, "Yo creo que es el collar. Pero no sé por qué. ¿Y qué vio?")

    def test_clean_whisper_acronym_loops(self):
        """Test stripping acronym repetition loops like 'El S.I.C.I. de la S.T.A.A.R...'."""
        sample = "Lanzó el conjuro. El S.I.C.I. de la S.T.A.A.R.E.A.N.T.I.F.A.R.E.A.L.S.A.P.A.R.O.U.D.E.R.A.I.N.A.F.C.I.A.N.N.A.R.E.A.R.E.A.L.S.A.T.E.I.F.A.R.E.A.N.N.E.A.R.E.A.N.S.E.N.E.S.I.C.I.A.N.E.L.T.A.R.E.A.R.E.A.R.E.A.T.E.A.R.E.A.R.E.A.R.E.A.N.E.T.E.R.A.R.E Entonces atacó."
        cleaned = clean_whisper_hallucinations(sample)
        self.assertNotIn("S.I.C.I.", cleaned)
        self.assertIn("Lanzó el conjuro.", cleaned)
        self.assertIn("Entonces atacó.", cleaned)

    def test_clean_whisper_ghost_subtitles_discard_pure_hallucination_lines(self):
        """Test discarding lines that only contain ghost subtitle or channel hallucinations."""
        lines = [
            "Subtitulado por la comunidad de Amara.org",
            "Subtítulos por Jnkoil",
            "Visita www.comunidad-dnd.es para más información.",
        ]
        sample = "\n".join(lines)
        cleaned = clean_whisper_hallucinations(sample)
        self.assertEqual(cleaned.strip(), "")

    def test_names_and_events_are_not_hallucinations_by_their_spelling(self):
        for line in ("Escuela de Lingüística de la PUCE", "Inauguración de la nueva sede.",
                     "Lavoratorio de Bundru", "Laboratorio de Bundru"):
            with self.subTest(line=line):
                self.assertEqual(clean_whisper_hallucinations(line), line)

    def test_clean_whisper_ghost_subtitles_trim_trailing_dialogue(self):
        """Test trimming trailing ghost phrases when attached to real dialogue."""
        sample = "Sir Yato desenfunda su espada y avanza con cuidado. Subtitulado por la Escuela de Lingüística"
        cleaned = clean_whisper_hallucinations(sample)
        self.assertEqual(cleaned.strip(), "Sir Yato desenfunda su espada y avanza con cuidado.")

    def test_clean_whisper_ghost_subtitles_preserves_legitimate_content(self):
        """Ensure genuine dialogue and narrative without hallucinations remain intact."""
        sample = "Halsey carga contra el Barlgura mientras la Hermana Lenure lanza Eldritch Blast."
        cleaned = clean_whisper_hallucinations(sample)
        self.assertEqual(cleaned.strip(), sample)


if __name__ == "__main__":
    unittest.main()
