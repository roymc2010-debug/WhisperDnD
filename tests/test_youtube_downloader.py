"""Unit tests for YouTube audio downloader."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.transcription.youtube_downloader import (
    download_youtube_audio,
    is_valid_youtube_url,
)


class TestYouTubeDownloader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_valid_youtube_url(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(is_valid_youtube_url(url))

        invalid_urls = [
            "",
            None,
            "https://google.com",
            "https://vimeo.com/123456",
            "not a url",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(is_valid_youtube_url(url))

    def test_download_youtube_audio_invalid_url(self):
        with self.assertRaises(ValueError):
            download_youtube_audio("https://invalid-site.com/video")

    def test_download_youtube_audio_mocked_success(self):
        try:
            import yt_dlp
        except ImportError:
            self.skipTest("yt-dlp is not installed yet")

        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl_instance = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

            dummy_dest = Path(__file__).resolve()  # existing file to pass is_file check
            mock_ydl_instance.extract_info.return_value = {
                "title": "sample_video",
                "requested_downloads": [{"filepath": str(dummy_dest)}],
            }

            url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            result_path = download_youtube_audio(url, output_dir=self.temp_dir)

            self.assertEqual(result_path, str(dummy_dest))
            mock_ydl_instance.extract_info.assert_called_once_with(url, download=True)

    def test_download_youtube_audio_progress_hook(self):
        try:
            import yt_dlp
        except ImportError:
            self.skipTest("yt-dlp is not installed yet")

        progress_calls = []

        def on_prog(pct, msg):
            progress_calls.append((pct, msg))

        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            captured_opts = {}

            def fake_ydl_init(opts):
                captured_opts.update(opts)
                mock_inst = MagicMock()
                dummy_dest = Path(__file__).resolve()
                mock_inst.extract_info.return_value = {
                    "title": "sample_video",
                    "requested_downloads": [{"filepath": str(dummy_dest)}],
                }
                mock_inst.__enter__.return_value = mock_inst
                return mock_inst

            mock_ydl_class.side_effect = fake_ydl_init

            url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            result_path = download_youtube_audio(url, output_dir=self.temp_dir, on_progress=on_prog)

            self.assertIn("progress_hooks", captured_opts)
            self.assertEqual(len(captured_opts["progress_hooks"]), 1)
            hook = captured_opts["progress_hooks"][0]

            # Trigger hook simulating 50% download (should map to 15% out of 30%)
            hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000})
            self.assertTrue(any(pct == 15 for pct, _ in progress_calls))

            # Trigger hook finished (should map to 30%)
            hook({"status": "finished"})
            self.assertTrue(any(pct == 30 for pct, _ in progress_calls))

    def test_download_youtube_audio_native_options(self):
        try:
            import yt_dlp
        except ImportError:
            self.skipTest("yt-dlp is not installed yet")

        captured_opts = {}

        def fake_ydl_init(opts):
            captured_opts.update(opts)
            mock_inst = MagicMock()
            dummy_dest = Path(__file__).resolve()
            mock_inst.extract_info.return_value = {
                "id": "dQw4w9WgXcQ",
                "title": "sample_video",
                "requested_downloads": [{"filepath": str(dummy_dest)}],
            }
            mock_inst.__enter__.return_value = mock_inst
            return mock_inst

        with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl_init):
            url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            download_youtube_audio(url, output_dir=self.temp_dir)

            self.assertEqual(captured_opts.get("format"), "bestaudio[ext=m4a]/bestaudio/best")
            self.assertIn("%(id)s.%(ext)s", captured_opts.get("outtmpl", ""))
            self.assertNotIn("postprocessors", captured_opts)


if __name__ == "__main__":
    unittest.main()
