from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_site import export_site
import check_deployment


class PublishingTests(unittest.TestCase):
    def test_accessible_private_source_fails_deployment_check(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(check_deployment, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "received HTTP 200"):
                check_deployment.check_route("/scripts/auto_news.py", 404)

    def test_not_found_is_required_for_private_routes_and_rejected_for_articles(self):
        with patch.object(check_deployment, "urlopen", side_effect=HTTPError("https://presence.news", 404, "Not found", {}, None)):
            check_deployment.check_route("/scripts/auto_news.py", 404)
            with self.assertRaisesRegex(RuntimeError, "received HTTP 404"):
                check_deployment.check_route("/articles/example/", 200)

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
