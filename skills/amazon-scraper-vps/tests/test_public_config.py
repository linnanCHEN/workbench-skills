"""Verify that public clients require explicit configuration without network I/O."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "public_vps_client", Path(__file__).resolve().parents[1] / "scripts" / "call_vps.py"
)
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class PublicConfigurationTests(unittest.TestCase):
    def test_missing_url_stops_before_credential_or_network_access(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(CLIENT, "read_windows_credential") as credential, patch.object(CLIENT.urllib.request, "urlopen") as network:
            with self.assertRaisesRegex(RuntimeError, "URL is required"):
                CLIENT.request("/health")
            credential.assert_not_called()
            network.assert_not_called()

    def test_unsafe_urls_are_rejected(self) -> None:
        for url in ("http://example.invalid", "https://user:password@example.invalid", "https://example.invalid?token=test", "https://example.invalid#fragment", "https://"):
            with self.subTest(url=url), patch.dict(os.environ, {"AMAZON_SCRAPER_VPS_URL": url}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "HTTPS base URL"):
                    CLIENT.api_credentials()

    def test_explicit_https_url_and_token_are_preserved(self) -> None:
        with patch.dict(os.environ, {"AMAZON_SCRAPER_VPS_URL": "https://example.invalid/amazon-scraper/", "AMAZON_SCRAPER_VPS_TOKEN": "TEST_ONLY_TOKEN"}, clear=True):
            self.assertEqual(CLIENT.api_credentials(True), ("https://example.invalid/amazon-scraper", "TEST_ONLY_TOKEN"))

    def test_missing_token_blocks_protected_operations(self) -> None:
        with patch.dict(os.environ, {"AMAZON_SCRAPER_VPS_URL": "https://example.invalid"}, clear=True), patch.object(CLIENT, "read_windows_credential", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "TOKEN is required"):
                CLIENT.api_credentials(True)


if __name__ == "__main__":
    unittest.main()
