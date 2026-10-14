from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_site import export_site


class PublishingTests(unittest.TestCase):
    def test_public_artifact_serves_articles_without_editorial_code_or_records(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            export_site(destination)
            for name in ("index.html", "news/index.html", "feed.xml", "CNAME", ".nojekyll", "assets/js/news-data.js", "articles/2026-10-14_ripple-meritz-korea-xrp/index.html"):
                self.assertTrue((destination / name).is_file(), name)
            for name in ("scripts", "docs", "tests", ".git", ".github", "README.md", "_config.yml"):
                self.assertFalse((destination / name).exists(), name)
            self.assertFalse(list(destination.rglob("*.py")))


if __name__ == "__main__":
    unittest.main()
