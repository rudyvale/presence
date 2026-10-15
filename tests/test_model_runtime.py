from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from start_news_model import safe_failure, verify_cached_blobs


class ModelRuntimeTests(unittest.TestCase):
    def test_cached_blobs_are_verified_and_corruption_requires_redownload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "blobs").mkdir()
            data = b"verified model configuration"
            blob = root / "blobs" / ("sha256-" + sha256(data).hexdigest())
            blob.write_bytes(data)
            self.assertTrue(verify_cached_blobs(root))
            blob.write_bytes(b"corrupt")
            self.assertFalse(verify_cached_blobs(root))
            self.assertFalse(blob.exists())

    def test_public_failure_diagnostic_does_not_echo_download_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "pull.log"
            log.write_text("Error: HTTP 429 https://storage.invalid/file?token=example")
            self.assertEqual(safe_failure(log), "model download returned HTTP 429")


if __name__ == "__main__":
    unittest.main()
