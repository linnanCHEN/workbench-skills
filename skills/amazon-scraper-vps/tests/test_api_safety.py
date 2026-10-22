import base64
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

CLIENT = Path(__file__).resolve().parents[1] / "scripts" / "call_vps.py"
spec = importlib.util.spec_from_file_location("vps_client", CLIENT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
HEALTH = {"status": "ok", "proxy_configured": True}
PRODUCTS = {"status": "SUCCESS", "products": [{"asin": "B000000001"}]}
PAGE = {"url": "https://www.amazon.com/dp/B000000001", "pages": 1}
IMAGE = "https://m.media-amazon.com/images/I/test.jpg"


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, content_type="application/json"):
        super().__init__(data)
        self.headers = Message()
        self.headers["content-type"] = content_type


class ApiSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_target_validation(self):
        for payload in [{"url": "https://amazon.com.evil.test/dp/x"}, {"url": "http://amazon.com/dp/x"}, {**PAGE, "pages": 0}, {**PAGE, "pages": True}, {**PAGE, "pages": 6}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                client.validate_operation("/scrape", "POST", payload)
        client.validate_operation("/scrape", "POST", PAGE)
        client.validate_operation("/image", "POST", {"url": IMAGE})
        client.validate_operation("/image", "POST", {"url": "https://images.amazon.com/images/I/test.jpg"})

    def test_proxy_false_blocks_business(self):
        with patch.object(client, "http_call", return_value=(200, {"status": "ok", "proxy_configured": False})) as call:
            status, _ = client.perform("https://example.test", "fixture", "/scrape", "POST", PAGE)
            self.assertEqual(status, 503)
            self.assertEqual(call.call_count, 1)

    def test_business_failure_and_empty_result_fail(self):
        for result in [{"status": "FAILED", "message": "secret-sentinel"}, {"status": "SUCCESS", "products": []}]:
            with patch.object(client, "http_call", side_effect=[(200, HEALTH), (200, result)]):
                status, safe = client.perform("https://example.test", "fixture", "/scrape", "POST", PAGE)
                self.assertEqual(status, 502)
                self.assertNotIn("secret-sentinel", json.dumps(safe))

    def test_success_preserves_parent_contract(self):
        with patch.object(client, "http_call", side_effect=[(200, HEALTH), (200, PRODUCTS)]):
            self.assertEqual(client.perform("https://example.test", "fixture", "/scrape", "POST", PAGE), (200, PRODUCTS))

    def test_http_401_does_not_expose_body_or_url(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://private.test", 401, "secret-sentinel", {}, io.BytesIO(b"secret-sentinel"))
        with patch.object(client.urllib.request, "build_opener", return_value=opener):
            status, result = client.http_call("https://example.test", "fixture", "/health", "GET", None)
        self.assertEqual(status, 401)
        self.assertNotIn("secret-sentinel", json.dumps(result))
        self.assertNotIn("private.test", json.dumps(result))

    def test_redirects_rejected(self):
        self.assertIsNone(client.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test"))

    def test_image_response_limit_and_type(self):
        for raw, content_type in [(b"text", "text/html"), (b"", "image/jpeg"), (b"x" * 17, "image/jpeg")]:
            with self.subTest(content_type=content_type), patch.object(client, "MAX_IMAGE_BYTES", 16), patch.object(client.urllib.request, "build_opener", return_value=Mock(open=Mock(return_value=Response(raw, content_type)))):
                self.assertEqual(client.http_call("https://example.test", "fixture", "/image", "POST", {"url": IMAGE})[0], 502)

    def test_image_saved_contract_accepts_path(self):
        data = b"\xff\xd8\xfffixture"
        result = {"image_base64": base64.b64encode(data).decode(), "content_type": "image/jpeg"}
        target = self.root / "nested" / "image.jpg"
        with patch.object(client, "request", return_value=(200, result)):
            status, saved = client.download_image(IMAGE, target)
        self.assertEqual(status, 200)
        self.assertEqual(saved["status"], "saved")
        self.assertEqual(saved["bytes"], len(data))
        self.assertEqual(target.read_bytes(), data)
        self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_invalid_image_never_overwrites_existing_file(self):
        target = self.root / "existing.jpg"
        target.write_bytes(b"existing-file")
        cases = [
            {"image_base64": base64.b64encode(b"\xff\xd8\xfffixture").decode()},
            {"image_base64": base64.b64encode(b"<html>error</html>").decode(), "content_type": "image/jpeg"},
            {"image_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode(), "content_type": "image/jpeg"},
        ]
        for result in cases:
            with self.subTest(result=result), patch.object(client, "request", return_value=(200, result)):
                self.assertEqual(client.download_image(IMAGE, target)[0], 502)
                self.assertEqual(target.read_bytes(), b"existing-file")
                self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_image_signature_matches_content_type(self):
        self.assertTrue(client.valid_image(b"\x89PNG\r\n\x1a\nfixture", "image/png"))
        self.assertTrue(client.valid_image(b"RIFF\x04\x00\x00\x00WEBP", "image/webp"))
        self.assertFalse(client.valid_image(b"<html>error</html>", "image/jpeg"))

    def test_cli_health_and_business_failures_exit_nonzero(self):
        for args, result in [(["client", "health"], (200, {"status": "ok", "proxy_configured": False})), (["client", "scrape", PAGE["url"]], (200, {"status": "FAILED"})), (["client", "health"], (401, {"error": "http_error"}))]:
            with patch.object(sys, "argv", args), patch.object(client, "request", return_value=result), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(client.main(), 1)

    def test_invalid_url_does_not_read_credentials(self):
        with patch.dict(os.environ, {"AMAZON_SCRAPER_VPS_URL": "http://localhost:8790"}), patch.object(client, "read_windows_credential", side_effect=AssertionError("must not read credentials")):
            with self.assertRaises(RuntimeError):
                client.request("/health")

    def test_private_profile_does_not_replace_missing_https_url(self):
        with patch.dict(os.environ, {"AMAZON_SCRAPER_VPS_CONFIG": "private-profile.json"}), patch.object(Path, "read_text", side_effect=AssertionError("must not inspect private profile")), patch.object(client, "read_windows_credential", side_effect=AssertionError("must not read credentials")):
            with self.assertRaisesRegex(RuntimeError, "URL is required"):
                client.request("/health")

    def test_default_private_profile_is_never_inspected(self):
        with patch.object(Path, "home", side_effect=AssertionError("must not discover private profile")):
            with self.assertRaisesRegex(RuntimeError, "URL is required"):
                client.request("/health")

    def test_invalid_target_stops_before_credential_or_network_access(self):
        with patch.object(client, "api_credentials", side_effect=AssertionError("must not read credentials")), patch.object(client, "http_call", side_effect=AssertionError("must not access network")):
            self.assertEqual(client.request("/scrape", "POST", {"url": "https://example.invalid"})[0], 400)

    def test_cli_missing_configuration_is_safe_nonzero(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["client", "health"]), contextlib.redirect_stdout(output):
            self.assertEqual(client.main(), 1)
        self.assertEqual(json.loads(output.getvalue()), {"error": "invalid_configuration"})

    def test_health_failure_preserves_status_without_private_body(self):
        with patch.object(client, "http_call", return_value=(401, {"error": "secret-sentinel"})):
            status, result = client.perform("https://example.invalid", "fixture", "/health", "GET", None)
        self.assertEqual(status, 401)
        self.assertNotIn("secret-sentinel", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
