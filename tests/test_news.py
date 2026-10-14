from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_catalog
import import_news


class NewsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ("assets/js", "assets/data", "scripts/templates"):
            (self.root / folder).mkdir(parents=True)
        template = Path(import_news.ROOT / "scripts/templates/news-article.html.tmpl").read_text()
        (self.root / "scripts/templates/news-article.html.tmpl").write_text(template)
        (self.root / "assets/js/news-data.js").write_text("window.PRESENCE_NEWS = [];\n")
        (self.root / "assets/data/author-bios.json").write_text(json.dumps({
            "authors": {"Presence Editorial": {"bio": "Presence Editorial is the editorial team behind Presence."}}
        }))
        self.source = self.root / "manuscript.txt"
        self.source.write_text("A report on markets\n\nAn introduction.\n\nThe full report, with <script>alert('x')</script> as literal text.\n\nSources for editorial verification:\n- An editor-only reference\n")
        self.addCleanup(patch.stopall)
        patch.object(import_news, "ROOT", self.root).start()
        patch.object(build_catalog, "ROOT", self.root).start()

    def import_story(self, slug="market-report"):
        return import_news.import_news(self.source, date(2026, 10, 8), slug, "A report summary.")

    def test_publication_contract_and_editor_notes(self):
        story = self.import_story()
        self.assertEqual(story["date"], "2026-10-08")
        self.assertEqual(story["type"], "NEWS")
        self.assertEqual(story["author"], "Presence Editorial")
        self.assertEqual(story["url"], "/articles/2026-10-08_market-report/")
        document = (self.root / story["url"].lstrip("/") / "index.html").read_text()
        self.assertIn('datetime="2026-10-08">October 8, 2026', document)
        self.assertNotIn("editor-only reference", document)
        self.assertIn("editor-only reference", (self.root / "docs/editorial/2026-10-08_market-report.md").read_text())

    def test_manuscript_text_is_escaped_and_preserved(self):
        story = self.import_story()
        document = (self.root / story["url"].lstrip("/") / "index.html").read_text()
        self.assertNotIn("<script>alert", document)
        self.assertIn("&lt;script&gt;alert", document)
        class Body(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inside = False
                self.text = []
            def handle_starttag(self, tag, attrs):
                if tag == "div" and dict(attrs).get("class") == "article__body": self.inside = True
            def handle_endtag(self, tag):
                if tag == "div": self.inside = False
            def handle_data(self, text):
                if self.inside: self.text.append(text)
        body = Body()
        body.feed(document)
        self.assertEqual(" ".join("".join(body.text).split()), "An introduction. The full report, with <script>alert('x')</script> as literal text.")

    def test_duplicate_import_preserves_existing_files(self):
        story = self.import_story()
        article = self.root / story["url"].lstrip("/") / "index.html"
        before = article.read_bytes(), (self.root / "assets/js/news-data.js").read_bytes()
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.import_story()
        self.assertEqual(before, (article.read_bytes(), (self.root / "assets/js/news-data.js").read_bytes()))

    def test_invalid_slug_cannot_escape_site_root(self):
        with self.assertRaises(ValueError):
            self.import_story("../escape")
        self.assertEqual(build_catalog.load_stories(), [])
        self.assertFalse((self.root / "articles").exists())

    def test_uppercase_editor_notes_and_dateline_are_not_body_copy(self):
        title, body, notes = import_news.parse_manuscript("A report\n\nIntroduction.\n\nOctober 14, 2026\n\nThe report body.\n\nSOURCES FOR EDITORIAL VERIFICATION\n\nAn editor note.")
        self.assertEqual(body, ["Introduction.", "The report body."])
        self.assertIn("An editor note.", notes)

    def test_sections_separate_reports_and_interviews(self):
        stories = [
            {"type": "NEWS", "category": "crypto", "title": "Protocol announcement"},
            {"type": "INTERVIEW", "category": "crypto", "title": "Founder interview"},
            {"type": "ARTICLE", "category": "technology", "title": "Software essay"},
        ]
        self.assertEqual([s["title"] for s in build_catalog.listing_stories(stories, "news")], ["Protocol announcement"])
        self.assertEqual([s["title"] for s in build_catalog.listing_stories(stories, "crypto")], ["Founder interview"])
        self.assertEqual([s["title"] for s in build_catalog.listing_stories(stories, "technology")], ["Software essay"])
        self.assertEqual(build_catalog.listing_stories(stories, "companies"), [])


if __name__ == "__main__":
    unittest.main()
