from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_site import export_site
import check_deployment


class PublishingTests(unittest.TestCase):
    def test_new_validation_versions_are_checked_on_the_public_site(self):
        root = check_deployment.ROOT
        history = json.loads((root / "docs/editorial/auto-news-history.json").read_text())
        record = {**history["items"][0], "format_version": 3}
        route = record["article_url"]
        document = (root / route.lstrip("/") / "index.html").read_bytes()
        image = (root / record["image"].lstrip("/")).read_bytes()
        news = f'<article class="news-card"><a href="{route}">Story</a><div class="news-card__media"><img src="{record["image"]}"></div></article>'.encode()
        responses = {route: document, record["image"]: image, "/news/": news}
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            ledger = temporary / "docs/editorial/auto-news-history.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({"items": [record]}))
            article = temporary / route.lstrip("/") / "index.html"
            article.parent.mkdir(parents=True)
            article.write_bytes(document)
            with patch.object(check_deployment, "ROOT", temporary), patch.dict("os.environ", {"EXPECTED_ARTICLES_JSON": "[]"}), patch.object(check_deployment, "check_route", side_effect=lambda path, status: responses.get(path, b"")) as fetch, patch("builtins.print"):
                check_deployment.main()
                fetch.assert_any_call(route, 200)

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
