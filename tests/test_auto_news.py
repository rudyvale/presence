from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_news
import news_quality
from news_source import extract_article


class AutomatedNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
        self.facts = [
            "Northstar Network announced that its custody access program will be expanded to institutions already working with the platform's existing partners.",
            "The first phase involves 40 institutions, with access initially offered through participating banks rather than direct registration with the network.",
            "The participating banks retain responsibility for their own customer checks, and the network does not replace their account approval procedures.",
            "The update adds a shared reporting interface that lets authorized institutions review the status of their custody arrangements through existing accounts.",
            "Institutions can continue using current custody arrangements during the rollout, and switching to the expanded program is voluntary for existing customers.",
            "The announcement does not include a public launch date for general registration, and access beyond the first phase remains conditional.",
            "Northstar said that service coverage will be introduced in stages, with the participating partners handling communication with their own institutional customers.",
            "The company has not supplied adoption forecasts or promised changes to fees, and the update concerns access and reporting rather than investment returns."
        ]
        self.report = {
            "title": "Northstar Extends Institutional Custody Access Through Bank Partners",
            "summary": "Northstar is expanding partner-based custody access, beginning with 40 institutions and a shared reporting interface.",
            "headings": ["Access through existing partners", "A phased introduction"],
            "paragraphs": [
                "Northstar Network is widening its custody program for organizations connected to its partner network. The announcement focuses on how those customers reach the service and monitor their arrangements, with the existing banking relationships remaining central to the proposed expansion.",
                "Access in the initial phase covers 40 institutions. Those organizations will reach the program through banks that already participate in the network, so the first group is tied to established customer relationships rather than an open registration process.",
                "Customer approval remains with each participating bank. Northstar's expanded access does not take over that responsibility or remove the procedures the banks apply to the institutions they serve. The partners continue to manage their own account checks.",
                "A shared reporting interface is another part of the update. Authorized institutional users will be able to inspect the status of custody arrangements from their current accounts, adding a reporting function alongside the partner-based route into the program.",
                "Existing customers have a choice about moving to the expanded offering. Their present custody arrangements can remain in use during the introduction, and the announcement does not require every institution to switch to the updated program at the same time.",
                "The rollout is intended to happen in stages. Partner banks will communicate with their institutional customers about the service coverage available to them. Northstar has left the timing of general registration open rather than announcing unrestricted access.",
                "The announcement offers no adoption forecast or commitment to a different fee structure. Its stated scope is access and reporting, while any wider availability remains conditional on later stages of the program rather than a completed general launch."
            ]
        }
        text = " ".join(self.facts) + " The original announcement provides detailed operational information about the proposed custody access program and the roles of its participants."
        self.item = {"url": "https://crypto.news/example-update/", "title": "Northstar announces a custody update", "description": text[:400], "published": self.now}
        self.researched = {**self.item, "facts": self.facts, "source": {"text": text, "word_count": len(text.split()), "sha256": "a" * 64, "extractor": ".entry-content", "reference_urls": []}}

    def test_feed_rejects_old_sponsored_and_foreign_entries(self):
        description = self.item["description"]
        data = f'''<rss><channel>
        <item><title>New update</title><link>https://crypto.news/new/?utm_source=feed</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><description>{description}</description></item>
        <item><title>Advertisement</title><link>https://crypto.news/ad/</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><category>Sponsored</category><description>{description}</description></item>
        <item><title>Old report</title><link>https://crypto.news/old/</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate><description>{description}</description></item>
        <item><title>Wrong host</title><link>https://example.com/post/</link><pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate><description>{description}</description></item>
        </channel></rss>'''.encode()
        self.assertEqual([item["url"] for item in auto_news.parse_feed(data, self.now)], ["https://crypto.news/new/"])

    def test_feed_failure_is_not_an_empty_feed(self):
        with self.assertRaises(ValueError):
            auto_news.parse_feed(b"<html>Access denied</html>", self.now)

    def test_limit_uses_moscow_day_and_does_not_fill_evening_slot_in_morning(self):
        history = {"items": [{"date": "2026-10-14", "source_url": "other"}]}
        self.assertEqual(auto_news.eligible_items([self.item], history, self.now), [])
        evening = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
        self.assertEqual(len(auto_news.eligible_items([self.item], history, evening)), 1)
        midnight = datetime(2026, 10, 14, 21, 30, tzinfo=timezone.utc)
        self.assertEqual(auto_news.eligible_items([self.item], {"items": []}, midnight), [])

    def test_duplicate_sources_are_not_published_again(self):
        history = {"items": [{"date": "2026-10-13", "source_url": self.item["url"]}]}
        self.assertEqual(auto_news.eligible_items([self.item, self.item], history, self.now), [])
        self.assertEqual(len(auto_news.eligible_items([self.item, self.item], {"items": []}, self.now)), 1)

    def test_complete_original_report_is_accepted(self):
        auto_news.validate_brief(self.report, self.researched)

    def test_private_factual_notes_can_preserve_exact_technical_source_terms(self):
        news_quality.validate_facts(self.facts, self.researched["source"]["text"])

    def test_excerpt_cannot_pass_as_a_complete_article(self):
        report = {**self.report, "paragraphs": self.report["paragraphs"][:2]}
        with self.assertRaises(ValueError):
            auto_news.validate_brief(report, self.researched)

    def test_incomplete_last_sentence_is_rejected_even_when_json_is_complete(self):
        paragraphs = [*self.report["paragraphs"][:-1], self.report["paragraphs"][-1].rstrip(".")]
        with self.assertRaisesRegex(ValueError, "complete sentences"):
            auto_news.validate_brief({**self.report, "paragraphs": paragraphs}, self.researched)

    def test_unsupported_figures_branding_and_tickers_are_rejected(self):
        for title in ("Custody access reaches 500 institutions", "Crypto.news publishes an update", "Read https://example.com", "Northstar PPLC custody program"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                auto_news.validate_brief({**self.report, "title": title}, self.researched)

    def test_quantity_scale_currency_and_percentage_are_preserved(self):
        news_quality.validate_numbers("138 million payments and $811 million, down 2%", "138,000,000 payments and $811,000,000, down 2 percent")
        news_quality.validate_numbers("a 5-year program", "a five-year program")
        with self.assertRaises(ValueError):
            news_quality.validate_numbers("2 percentage points", "2 percent")
        for output in ("138 billion payments", "$138 million", "811 payments", "2%", "billions of payments", "a billion payments"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "magnitude"):
                news_quality.validate_numbers(output, "138 million payments and $811 million")

    def test_unquantified_billions_in_headline_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "magnitude"):
            auto_news.validate_brief({**self.report, "title": "Billions of institutions enter custody program"}, self.researched)

    def test_extended_source_copy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "source phrase"):
            news_quality.validate_originality(self.researched["source"]["text"], self.researched["source"]["text"])

    def test_full_article_extraction_excludes_navigation_and_related_content(self):
        paragraphs = "".join(f"<p>{fact}</p>" for fact in self.facts) + "<p>The operational update describes how participating institutions will continue working through their existing banking relationships as the reporting service becomes available.</p>"
        data = f'<html><nav><p>Navigation poison</p></nav><article><div class="post-detail__content">{paragraphs}<div class="related-posts"><p>Related poison</p></div></div></article></html>'.encode()
        source = extract_article(data, self.item["url"])
        self.assertGreaterEqual(source["word_count"], 180)
        self.assertIn("40 institutions", source["text"])
        self.assertNotIn("poison", source["text"])
        self.assertEqual(source["extractor"], ".post-detail__content")

    def test_full_article_fetch_does_not_fall_back_to_metadata_excerpt(self):
        with self.assertRaisesRegex(ValueError, "RSS excerpt"):
            extract_article(b'<article><p>A truncated news announcement.</p></article>', self.item["url"])

    def test_default_backend_needs_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(auto_news, "generate_local_response", return_value=self.report) as local, patch.object(auto_news, "generate_api_response") as api:
            self.assertEqual(auto_news.request_model([]), self.report)
            local.assert_called_once()
            api.assert_not_called()

    def test_missing_api_key_stops_before_inference(self):
        with patch.dict("os.environ", {"NEWS_AI_TOKEN": "", "NEWS_AI_BACKEND": "api"}):
            with self.assertRaisesRegex(ValueError, "NEWS_AI_TOKEN"):
                auto_news.request_model([])

    def test_local_request_has_fixed_loopback_and_no_credentials(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"message": {"content": json.dumps(self.report)}, "done_reason": "stop"}).encode()
        response.__enter__.return_value = response
        with patch.dict("os.environ", {"NEWS_AI_TOKEN": "test-only"}), patch.object(auto_news, "build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(auto_news.generate_local_response([]), self.report)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
            self.assertNotIn("Authorization", request.headers)

    def test_truncated_model_response_is_never_published(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"message": {"content": json.dumps(self.report)}, "done_reason": "length"}).encode()
        response.__enter__.return_value = response
        with patch.object(auto_news, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, "truncated"):
                auto_news.generate_local_response([])

    def test_expired_budget_defers_work_before_source_or_model_calls(self):
        with patch.object(auto_news, "PROCESSING_DEADLINE", 1), patch.object(auto_news, "research_item") as research:
            with self.assertRaises(auto_news.EditorialBudgetExceeded):
                auto_news.prepare_report(self.item)
            research.assert_not_called()

    def test_grounding_requires_support_and_substantive_coverage(self):
        for review in ({"supported": False, "covered_facts": list(range(8))}, {"supported": "true", "covered_facts": list(range(8))}, {"supported": True, "covered_facts": [0, 1]}, {"supported": True, "covered_facts": [99]}):
            with self.subTest(review=review), patch.object(auto_news, "request_model", return_value=review), self.assertRaises(ValueError):
                auto_news.validate_grounding(self.report, self.researched)
        with patch.object(auto_news, "request_model", return_value={"supported": True, "covered_facts": list(range(8))}):
            auto_news.validate_grounding(self.report, self.researched)

    def test_report_and_illustration_are_published_once_with_source_audit(self):
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
            with patch.object(import_news, "ROOT", root), patch.object(build_catalog, "ROOT", root), patch.object(auto_news, "ROOT", root), patch.object(auto_news, "HISTORY", root / "docs/editorial/history.json"), patch.object(auto_news, "prepare_report", return_value=(self.report, self.researched)), patch.object(auto_news, "notice"), patch("build_seo.main") as build:
                route = auto_news.publish_one([self.item], self.now)
                story = build_catalog.load_stories()[0]
                document = (root / route.lstrip("/") / "index.html").read_text()
                self.assertIn('class="article__hero-media"', document)
                self.assertEqual(document.split('class="article__body">', 1)[1].split('</div>', 1)[0].count("<h2>"), 2)
                self.assertTrue((root / story["image"].lstrip("/")).exists())
                record = auto_news.load_history()["items"][0]
                self.assertGreaterEqual(record["word_count"], 220)
                self.assertEqual(record["format_version"], 2)
                self.assertEqual(record["source_snapshot"]["fact_count"], len(self.facts))
                self.assertNotIn("facts", record["source_snapshot"])
                import check_deployment
                self.assertEqual(check_deployment.verify_report(document.encode(), record), story["image"])
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    check_deployment.verify_report(document.replace("Northstar Network", "A different company", 1).encode(), record)
                self.assertNotIn("research facts", document)
                build.assert_called_once()
                self.assertIsNone(auto_news.publish_one([self.item], self.now))
                auto_news.publish_report(self.researched, self.report, self.now, record)
                self.assertEqual(len(build_catalog.load_stories()), 1)
                self.assertEqual(auto_news.load_history()["items"][0]["date"], "2026-10-14")


if __name__ == "__main__":
    unittest.main()
