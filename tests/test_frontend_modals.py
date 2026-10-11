"""Unit tests for Frontend Modals DOM and Interaction Contracts.

Ensures that all overlay modals across WhisperDnD and Work & Study:
1. Exist in static/index.html with valid backdrop click handlers.
2. Have inner dialog boxes with 'pointer-events-auto' to prevent click passthrough.
3. Have initial 'pointer-events-none' when hidden to avoid blocking page interaction.
4. Have paired JavaScript functions that toggle 'pointer-events-auto' / 'pointer-events-none'.
5. Have a registered global 'Escape' key handler so users can never be trapped.
6. Use cache-busted script tags in static/index.html.
"""

import re
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = WORKSPACE_ROOT / "static"
INDEX_HTML = STATIC_DIR / "index.html"
JS_DIR = STATIC_DIR / "js"


class TestFrontendModalsIntegrity(unittest.TestCase):
    """Verifies HTML and JavaScript modal interaction and pointer-events contracts."""

    @classmethod
    def setUpClass(cls):
        cls.html_content = INDEX_HTML.read_text(encoding="utf-8")
        cls.app_js = (JS_DIR / "app.js").read_text(encoding="utf-8")
        cls.wiki_js = (JS_DIR / "wiki.js").read_text(encoding="utf-8")
        cls.audio_js = (JS_DIR / "audio.js").read_text(encoding="utf-8")
        cls.notes_js = (JS_DIR / "notes.js").read_text(encoding="utf-8")

    def test_modals_exist_in_html(self):
        """All critical overlay modals must be defined in index.html."""
        expected_modals = [
            "campaignManagerModal",
            "mergeEntityModal",
            "tunnelModal",
            "backupFallbackModal",
            "modalAddGlossaryTerm",
        ]
        for modal_id in expected_modals:
            with self.subTest(modal=modal_id):
                pattern = rf'id="{modal_id}"'
                self.assertIn(
                    f'id="{modal_id}"',
                    self.html_content,
                    f"Modal '{modal_id}' not found in static/index.html",
                )

    def test_modal_inner_boxes_have_pointer_events_auto(self):
        """Inner dialog boxes must have pointer-events-auto to capture clicks and prevent passthrough."""
        inner_box_ids = [
            "campaignManagerModalBox",
            "mergeEntityModalBox",
            "tunnelModalBox",
            "backupFallbackModalBox",
            "modalAddGlossaryTermBox",
        ]
        for box_id in inner_box_ids:
            with self.subTest(box=box_id):
                # Check for id="box_id" class="... pointer-events-auto ..."
                match = re.search(
                    rf'id="{box_id}"[^>]*class="([^"]*)"',
                    self.html_content,
                )
                self.assertIsNotNone(match, f"Inner box '{box_id}' not found in index.html")
                classes = match.group(1).split()
                self.assertIn(
                    "pointer-events-auto",
                    classes,
                    f"Inner box '{box_id}' must contain 'pointer-events-auto' to intercept clicks.",
                )

    def test_modal_outer_wrappers_have_pointer_events_none_initially(self):
        """When hidden, outer modal wrappers must have pointer-events-none so they don't block clicks."""
        modal_ids = [
            "campaignManagerModal",
            "mergeEntityModal",
            "tunnelModal",
            "backupFallbackModal",
            "modalAddGlossaryTerm",
        ]
        for modal_id in modal_ids:
            with self.subTest(modal=modal_id):
                match = re.search(
                    rf'id="{modal_id}"[^>]*class="([^"]*)"',
                    self.html_content,
                )
                self.assertIsNotNone(match, f"Modal '{modal_id}' not found in index.html")
                classes = match.group(1).split()
                self.assertIn(
                    "pointer-events-none",
                    classes,
                    f"Modal '{modal_id}' must have 'pointer-events-none' when initially hidden.",
                )
                self.assertIn(
                    "hidden",
                    classes,
                    f"Modal '{modal_id}' must have 'hidden' class initially.",
                )

    def test_modal_outer_wrappers_have_backdrop_close_handler(self):
        """Modal wrappers must have an onclick handler to close when clicking the backdrop."""
        modal_ids = [
            "campaignManagerModal",
            "mergeEntityModal",
            "tunnelModal",
            "backupFallbackModal",
            "modalAddGlossaryTerm",
        ]
        for modal_id in modal_ids:
            with self.subTest(modal=modal_id):
                match = re.search(
                    rf'<div[^>]*id="{modal_id}"[^>]*onclick="([^"]*)"',
                    self.html_content,
                )
                self.assertIsNotNone(
                    match,
                    f"Modal '{modal_id}' must define an onclick backdrop handler on outer container.",
                )
                handler = match.group(1)
                self.assertIn(
                    "event.target === this",
                    handler,
                    f"Modal '{modal_id}' handler must check 'event.target === this' to close only on backdrop clicks.",
                )

    def test_campaign_manager_modal_js_toggles_pointer_events(self):
        """toggleCampaignManagerModal in app.js must correctly add/remove pointer-events classes."""
        match = re.search(r'async function toggleCampaignManagerModal\([^)]*\)\s*\{([\s\S]*?)\nfunction renderCampaignManagerList', self.app_js)
        self.assertIsNotNone(match, "Function toggleCampaignManagerModal not found in app.js")
        func_body = match.group(1)
        self.assertIn(
            'modal.classList.remove("opacity-0", "pointer-events-none")',
            func_body,
            "toggleCampaignManagerModal must remove 'pointer-events-none' when opening.",
        )
        self.assertIn(
            'modal.classList.add("opacity-100", "pointer-events-auto")',
            func_body,
            "toggleCampaignManagerModal must add 'pointer-events-auto' when opening.",
        )
        self.assertIn(
            'modal.classList.remove("opacity-100", "pointer-events-auto")',
            func_body,
            "toggleCampaignManagerModal must remove 'pointer-events-auto' when closing.",
        )
        self.assertIn(
            'modal.classList.add("opacity-0", "pointer-events-none")',
            func_body,
            "toggleCampaignManagerModal must restore 'pointer-events-none' when closing.",
        )

    def test_tunnel_modal_js_toggles_pointer_events(self):
        """openTunnelModal and closeTunnelModal in app.js must toggle pointer-events."""
        match_open = re.search(r'function openTunnelModal\([^)]*\)\s*\{([\s\S]*?)\nfunction closeTunnelModal', self.app_js)
        match_close = re.search(r'function closeTunnelModal\([^)]*\)\s*\{([\s\S]*?)\nfunction copyTunnelCmd', self.app_js)
        self.assertIsNotNone(match_open, "openTunnelModal not found in app.js")
        self.assertIsNotNone(match_close, "closeTunnelModal not found in app.js")
        open_body = match_open.group(1)
        close_body = match_close.group(1)

        self.assertIn('pointer-events-none', open_body, "openTunnelModal must remove 'pointer-events-none'.")
        self.assertIn('pointer-events-auto', open_body, "openTunnelModal must add 'pointer-events-auto'.")
        self.assertIn('pointer-events-auto', close_body, "closeTunnelModal must remove 'pointer-events-auto'.")
        self.assertIn('pointer-events-none', close_body, "closeTunnelModal must restore 'pointer-events-none'.")

    def test_merge_entity_modal_js_toggles_pointer_events(self):
        """toggleMergeEntityModal in wiki.js must toggle pointer-events."""
        match = re.search(r'function toggleMergeEntityModal\([^)]*\)\s*\{([\s\S]*?)\nfunction openMergeEntityModal', self.wiki_js)
        self.assertIsNotNone(match, "toggleMergeEntityModal not found in wiki.js")
        func_body = match.group(1)

        self.assertIn('pointer-events-none', func_body, "toggleMergeEntityModal must remove 'pointer-events-none' when opening.")
        self.assertIn('pointer-events-auto', func_body, "toggleMergeEntityModal must add 'pointer-events-auto' when opening.")
        self.assertIn('pointer-events-auto', func_body, "toggleMergeEntityModal must remove 'pointer-events-auto' when closing.")
        self.assertIn('pointer-events-none', func_body, "toggleMergeEntityModal must restore 'pointer-events-none' when closing.")

    def test_glossary_modal_js_toggles_pointer_events(self):
        """openAddGlossaryModal and closeAddGlossaryModal in notes.js must toggle pointer-events."""
        match_open = re.search(r'function openAddGlossaryModal\([^)]*\)\s*\{([\s\S]*?)\nfunction closeAddGlossaryModal', self.notes_js)
        match_close = re.search(r'function closeAddGlossaryModal\([^)]*\)\s*\{([\s\S]*?)\nasync function saveNewGlossaryTerm', self.notes_js)
        self.assertIsNotNone(match_open, "openAddGlossaryModal not found in notes.js")
        self.assertIsNotNone(match_close, "closeAddGlossaryModal not found in notes.js")
        open_body = match_open.group(1)
        close_body = match_close.group(1)

        self.assertIn('pointer-events-none', open_body, "openAddGlossaryModal must remove 'pointer-events-none'.")
        self.assertIn('pointer-events-auto', open_body, "openAddGlossaryModal must add 'pointer-events-auto'.")
        self.assertIn('pointer-events-auto', close_body, "closeAddGlossaryModal must remove 'pointer-events-auto'.")
        self.assertIn('pointer-events-none', close_body, "closeAddGlossaryModal must restore 'pointer-events-none'.")

    def test_global_escape_key_listener_present(self):
        """app.js must register a global keydown handler for 'Escape' to dismiss open modals."""
        self.assertIn(
            'window.addEventListener("keydown"',
            self.app_js,
            "app.js must register a window keydown listener.",
        )
        self.assertIn(
            'e.key === "Escape"',
            self.app_js,
            "app.js keydown listener must check for the Escape key.",
        )
        self.assertIn(
            "toggleCampaignManagerModal(false)",
            self.app_js,
            "Escape listener must be capable of closing campaignManagerModal.",
        )

    def test_script_tags_have_cache_busting_versions(self):
        """All modular scripts in index.html must have a '?v=' version string."""
        script_matches = re.findall(r'<script src="(/static/js/[^"]+)"', self.html_content)
        self.assertGreater(len(script_matches), 0, "No modular script tags found in index.html")
        for src in script_matches:
            with self.subTest(script=src):
                self.assertIn(
                    "?v=",
                    src,
                    f"Script tag '{src}' is missing cache-busting parameter '?v='",
                )


if __name__ == "__main__":
    unittest.main()
