from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_news


class AutomatedNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
        self.item = {"url": "https://crypto.news/example-update/", "title": "Protocol announces a custody update", "description": "The network announced changes to custody services and described how institutions will be able to access the updated platform through its existing partners.", "published": self.now}
        self.brief = {
            "title": "Custody services expand for institutional users",
            "summary": "A protocol update focuses on institutional custody access through existing partners.",
            "paragraphs": [
                "A network has outlined an update to its custody offering, placing institutional access at the center of the announcement. The plan relies on partners already connected to its platform, rather than presenting the service as a separate product. Custody remains a practical consideration for organizations seeking to manage digital assets through established operating arrangements.",
                "The announcement describes a change in the services available to those institutions. It does not by itself establish how widely the updated offering will be adopted. The details of access and the role of the network's partners are the central elements of the update, while subsequent uptake will depend on how institutions choose to use the service."
            ],
        }

    def test_feed_rejects_old_sponsored_and_foreign_entries(self):
        description = self.item["description"]
        data = f'''<rss><channel>
        <item><title>New update</title><link>https://crypto.news/new/?utm_source=feed</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><description>{description}</description></item>
        <item><title>Advertisement</title><link>https://crypto.news/ad/</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><category>Sponsored</category><description>{description}</description></item>
        <item><title>Old report</title><link>https://crypto.news/old/</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate><description>{description}</description></item>
        <item><title>Wrong host</title><link>https://example.com/post/</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><description>{description}</description></item>
        </channel></rss>'''.encode()
        items = auto_news.parse_feed(data, self.now)
        self.assertEqual([item["url"] for item in items], ["https://crypto.news/new/"])

    def test_feed_failure_is_not_treated_as_an_empty_feed(self):
        with self.assertRaises(ValueError):
            auto_news.parse_feed(b"<html>Access denied</html>", self.now)

    def test_daily_limit_uses_moscow_day_boundary(self):
        now = datetime(2026, 10, 14, 21, 30, tzinfo=timezone.utc)
        history = {"items": [{"date": "2026-10-15", "source_url": "a"}, {"date": "2026-10-15", "source_url": "b"}]}
        self.assertEqual(auto_news.eligible_items([self.item], history, now), [])

    def test_duplicate_sources_are_not_published_again(self):
        history = {"items": [{"date": "2026-10-13", "source_url": self.item["url"]}]}
        self.assertEqual(auto_news.eligible_items([self.item, self.item], history, self.now), [])
        self.assertEqual(len(auto_news.eligible_items([self.item, self.item], {"items": []}, self.now)), 1)

    def test_valid_original_brief_is_accepted(self):
        auto_news.validate_brief(self.brief, self.item)

    def test_unsupported_figures_and_source_branding_are_rejected(self):
        for title in ("Custody update reaches 500 institutions", "Crypto.news publishes an update", "Read https://example.com for the update"):
            with self.subTest(title=title):
                with self.assertRaises(ValueError):
                    auto_news.validate_brief({**self.brief, "title": title}, self.item)

    def test_source_sentence_copy_is_rejected(self):
        brief = {**self.brief, "paragraphs": [self.item["description"] + " " + self.brief["paragraphs"][0], self.brief["paragraphs"][1]]}
        with self.assertRaisesRegex(ValueError, "source phrase"):
            auto_news.validate_brief(brief, self.item)

    def test_missing_key_stops_before_network_inference(self):
        with patch.dict("os.environ", {"NEWS_AI_TOKEN": "", "NEWS_AI_BACKEND": "api"}):
            with self.assertRaisesRegex(ValueError, "NEWS_AI_TOKEN"):
                auto_news.generate_brief(self.item)

    def test_default_backend_uses_local_model_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(auto_news, "generate_local_brief", return_value=self.brief) as local, patch.object(auto_news, "generate_api_brief") as api:
            self.assertEqual(auto_news.generate_brief(self.item), self.brief)
            local.assert_called_once_with(self.item)
            api.assert_not_called()

    def test_local_request_uses_fixed_loopback_and_never_sends_credentials(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.read.return_value = json.dumps({"message": {"content": json.dumps(self.brief)}}).encode()
        response.__enter__.return_value = response
        with patch.dict("os.environ", {"NEWS_AI_TOKEN": "test-only", "NEWS_AI_ENDPOINT": "https://example.com"}), patch.object(auto_news, "build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(auto_news.generate_local_brief(self.item), self.brief)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
            self.assertNotIn("Authorization", request.headers)
            self.assertFalse(json.loads(request.data)["stream"])

    def test_unknown_backend_stops_before_inference(self):
        with patch.dict("os.environ", {"NEWS_AI_BACKEND": "unknown"}):
            with self.assertRaisesRegex(ValueError, "NEWS_AI_BACKEND"):
                auto_news.generate_brief(self.item)

    def test_pipeline_publishes_once_and_records_source(self):
        import build_catalog
        import import_news
        template = (import_news.ROOT / "scripts/templates/news-article.html.tmpl").read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("assets/js", "assets/data", "scripts/templates"):
                (root / folder).mkdir(parents=True)
            (root / "assets/js/news-data.js").write_text("window.PRESENCE_NEWS = [];\n")
            (root / "assets/data/author-bios.json").write_text(json.dumps({"authors": {"Presence Editorial": {"bio": "Presence Editorial is the editorial team."}}}))
            (root / "scripts/templates/news-article.html.tmpl").write_text(template)
            with patch.object(import_news, "ROOT", root), patch.object(build_catalog, "ROOT", root), patch.object(auto_news, "HISTORY", root / "docs/editorial/history.json"), patch.object(auto_news, "generate_brief", return_value=self.brief), patch("build_seo.main") as build:
                route = auto_news.publish_one([self.item], self.now)
                self.assertTrue(route.startswith("/articles/2026-10-14_"))
                self.assertTrue((root / route.lstrip("/") / "index.html").exists())
                self.assertEqual(auto_news.load_history()["items"][0]["source_url"], self.item["url"])
                self.assertIsNone(auto_news.publish_one([self.item], self.now))
                self.assertEqual(len(build_catalog.load_stories()), 1)
                build.assert_called_once()


if __name__ == "__main__":
    unittest.main()
