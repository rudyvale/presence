from hashlib import sha256
from html import escape
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_news
from check_news_sources import metric_contexts, verify_source
import test_auto_news


class NewsSourceAuditTests(unittest.TestCase):
    def test_metric_diagnostics_expose_numbers_without_source_prose(self):
        contexts = metric_contexts({"text": "Open interest was $140.9 billion after a 2% decline.\n\nRetail sales rose 0.5%."})
        self.assertIn(("1.409E+11", "$"), contexts["open_interest"][0])
        self.assertIn(("2", "percent"), contexts["open_interest"][0])
        self.assertIn(("0.5", "percent"), contexts["retail_sales"][0])
        self.assertNotIn("decline", str(contexts))

    def setUp(self):
        fixture = test_auto_news.AutomatedNewsTests()
        fixture.setUp()
        self.fixture = fixture
        report = fixture.report
        blocks = [f'<p>{escape(paragraph)}</p>' for paragraph in report["paragraphs"]]
        blocks.insert(2, f'<h2>{escape(report["headings"][0])}</h2>')
        blocks.insert(-2, f'<h2>{escape(report["headings"][1])}</h2>')
        self.document = f'<h1 class="article__title">{escape(report["title"])}</h1><div class="article__body">' + "".join(blocks) + "</div>"
        self.record = {"source_snapshot": {"headline": fixture.item["title"]}, "word_count": len(" ".join(report["paragraphs"]).split()), "body_sha256": sha256(auto_news.body_text(self.document).encode()).hexdigest()}

    def test_final_editorial_copy_is_checked_against_source_and_audit(self):
        verify_source(self.record, self.fixture.report, self.document, self.fixture.researched["source"])
        changed = self.document.replace("40 institutions", "400 institutions")
        updated = {**self.record, "body_sha256": sha256(auto_news.body_text(changed).encode()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "Unsupported number"):
            verify_source(updated, self.fixture.report, changed, self.fixture.researched["source"])
        with self.assertRaisesRegex(ValueError, "editorial audit"):
            verify_source({**self.record, "body_sha256": "0" * 64}, self.fixture.report, self.document, self.fixture.researched["source"])


if __name__ == "__main__":
    unittest.main()
