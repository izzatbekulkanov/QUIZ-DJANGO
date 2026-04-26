import tempfile
from pathlib import Path

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils.http import http_date

from core.media_views import serve_media_file


class MediaServingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_serve_media_file_without_if_modified_since_header(self):
        media_root = Path(self.temp_dir.name)
        target_file = media_root / "system" / "logo" / "logos.jpg"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(b"test-image")

        with override_settings(MEDIA_ROOT=media_root):
            response = serve_media_file(
                self.factory.get("/media/system/logo/logos.jpg"),
                "system/logo/logos.jpg",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Length"], str(target_file.stat().st_size))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_serve_media_file_returns_not_modified_for_matching_header(self):
        media_root = Path(self.temp_dir.name)
        target_file = media_root / "system" / "favicon" / "university_1.png"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(b"test-image")
        modified_header = http_date(target_file.stat().st_mtime)

        with override_settings(MEDIA_ROOT=media_root):
            response = serve_media_file(
                self.factory.get(
                    "/media/system/favicon/university_1.png",
                    HTTP_IF_MODIFIED_SINCE=modified_header,
                ),
                "system/favicon/university_1.png",
            )

        self.assertEqual(response.status_code, 304)
