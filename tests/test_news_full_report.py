from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_news
import news_full_report
import news_quality
import news_jobs
import test_auto_news
import test_news_jobs


class FullNewsTests(unittest.TestCase):
    def setUp(self):
        fixture = test_auto_news.AutomatedNewsTests()
        fixture.setUp()
        self.report = fixture.report
        self.item = {**fixture.researched, "length_policy": 2}
        self.profile = news_quality.full_length_profile(self.item["source"]["word_count"])

    def test_full_source_word_count_is_the_lower_bound_and_filler_cannot_exceed_the_cap(self):
        profile = news_quality.full_length_profile(904)
        self.assertEqual(profile["minimum"], 904)
        for words in (446, 903, 1041):
            with self.subTest(words=words), self.assertRaisesRegex(ValueError, "preserve source length"):
                news_quality.validate_completeness({"paragraphs": [" ".join(["word"] * words)]}, 904, 2)
        for words in (904, 1000, 1040):
            news_quality.validate_completeness({"paragraphs": [" ".join(["word"] * words)]}, 904, 2)

    def test_schema_cannot_generate_paragraphs_too_short_for_the_complete_article(self):
        item = {**self.item, "source": {**self.item["source"], "word_count": 904}}
        pattern = auto_news.paragraph_schema(item)["properties"]["text"]["pattern"]
        for words in (48, 51, 54):
            self.assertIsNotNone(re.fullmatch(pattern, " ".join(["word"] * words) + "."))
        for words in (35, 47, 55):
            self.assertIsNone(re.fullmatch(pattern, " ".join(["word"] * words) + "."))

    def test_long_features_are_skipped_instead_of_becoming_short_summaries(self):
        with self.assertRaisesRegex(ValueError, "must not be condensed"):
            news_quality.full_length_profile(4000)

    def test_research_keeps_complete_evidence_without_a_twelve_fact_summary(self):
        source = {**self.item["source"], "text": "\n\n".join(self.item["facts"]) + "\n\nThe original announcement provides detailed operational information about the proposed custody access program and the roles of its participants."}
        with patch.object(auto_news, "fetch_article", return_value=source), patch.object(auto_news, "request_model") as model, patch.object(auto_news, "notice"):
            item = auto_news.research_item(self.item)
        self.assertEqual(item["length_policy"], 2)
        self.assertGreaterEqual(item["source"]["research_word_count"], source["word_count"] * 0.8)
        model.assert_not_called()
        for fact in self.item["facts"]:
            self.assertIn(fact, item["facts"])

    def plan(self):
        return {**{key: self.report[key] for key in ("title", "summary", "headings")}, "paragraphs": [{"facts": ids} for ids in ([0, 1], [2], [3], [4], [5], [6, 7])]}

    def test_an_outline_omitting_source_details_is_rejected_before_writing(self):
        plan = self.plan()
        plan["paragraphs"] = [{"facts": [0]} for _ in range(self.profile["paragraphs"])]
        with patch.object(auto_news, "request_model", return_value=plan) as model, self.assertRaisesRegex(ValueError, "omits evidence"):
            news_full_report.plan_article(self.item, self.profile)
        self.assertEqual(model.call_count, 2)

    def test_only_the_failed_small_section_is_regenerated(self):
        metadata = {key: self.report[key] for key in ("title", "summary", "headings")}
        assignments = [{"facts": [index]} for index in range(4)]
        good = {"paragraphs": [{"text": paragraph, "facts": [index]} for index, paragraph in enumerate(self.report["paragraphs"][:4])]}
        bad = deepcopy(good)
        bad["paragraphs"][1]["text"] = bad["paragraphs"][1]["text"].replace("40", "400")
        with patch.object(auto_news, "request_model", side_effect=[bad, good]) as model, patch.object(auto_news, "repair_paragraph_evidence", side_effect=lambda piece, item, ids: (piece, ids)), patch.object(auto_news, "polish_originality", side_effect=lambda piece, item, ids: piece), patch.object(news_full_report, "review_piece"), patch.object(auto_news, "notice"):
            piece, ids = news_full_report.write_piece(self.item, metadata, assignments, "Earlier verified context.", self.profile)
        self.assertEqual(piece["paragraphs"], self.report["paragraphs"][:4])
        self.assertEqual(ids, [[0], [1], [2], [3]])
        self.assertEqual(model.call_count, 2)
        correction = json.loads(model.call_args.args[0][-1]["content"])
        self.assertIn("Unsupported number", correction["required_correction"])
        self.assertIn("400", correction["previous_draft"]["paragraphs"][1]["text"])

    def test_claim_review_must_cover_the_actual_cited_evidence(self):
        piece = {**self.report, "paragraphs": self.report["paragraphs"][:2]}
        with patch.object(auto_news, "request_model", return_value={"supported": True, "issues": [], "covered_facts": [0]}), self.assertRaisesRegex(ValueError, "omit factual evidence"):
            news_full_report.review_piece(piece, self.item, [[0], [1]])

    def test_metadata_review_does_not_require_another_complete_article(self):
        metadata = {key: self.report[key] for key in ("title", "summary", "headings")}
        with patch.object(auto_news, "request_model", return_value={"supported": True, "issues": []}) as model:
            self.assertEqual(news_full_report.review_metadata(metadata, self.item), metadata)
        self.assertNotIn("paragraphs", json.loads(model.call_args.args[0][1]["content"])["metadata"])

    def test_full_pipeline_assembles_verified_groups_and_preserves_length(self):
        plan = self.plan()
        plan["paragraphs"] = [{"facts": [index]} for index in range(5)] + [{"facts": [5, 6, 7]}]
        ending = "The introduction remains phased rather than open to everyone. Partner banks will contact their institutional customers about available services. No public date for general registration, adoption forecast or promise of different fees accompanies the update at this stage."
        first = {"paragraphs": [{"text": paragraph, "facts": [index]} for index, paragraph in enumerate(self.report["paragraphs"][:4])]}
        last = {"paragraphs": [{"text": self.report["paragraphs"][4], "facts": [4]}, {"text": ending, "facts": [5, 6, 7]}]}
        responses = [plan, first, {"supported": True, "issues": [], "covered_facts": [0, 1, 2, 3]}, last, {"supported": True, "issues": [], "covered_facts": [4, 5, 6, 7]}, {"supported": True, "issues": []}]
        with patch.object(auto_news, "request_model", side_effect=responses) as model, patch.object(auto_news, "notice"):
            report = news_full_report.prepare_full_report(self.item)
        self.assertEqual(len(report["paragraphs"]), 6)
        self.assertEqual(report["paragraphs"][:5], self.report["paragraphs"][:5])
        self.assertEqual(report["paragraphs"][-1], ending)
        news_quality.validate_completeness(report, self.item["source"]["word_count"], 2)
        self.assertEqual(model.call_count, 6)
        self.assertEqual(set(report), {"title", "summary", "headings", "paragraphs"})

    def test_publisher_independently_rejects_a_shortened_current_policy_artifact(self):
        fixture = test_news_jobs.NewsJobTests()
        fixture.setUp()
        receipt = fixture.receipt()
        receipt["item"]["length_policy"] = 2
        receipt["item"]["source"]["word_count"] = 904
        receipt["sha256"] = news_jobs.digest({key: value for key, value in receipt.items() if key != "sha256"})
        with self.assertRaisesRegex(ValueError, "preserve source length"):
            news_jobs.validate_receipt(receipt, fixture.job())

    def test_full_length_plan_cannot_be_downgraded_to_legacy_summary_rules(self):
        fixture = test_news_jobs.NewsJobTests()
        fixture.setUp()
        receipt = fixture.receipt()
        with self.assertRaisesRegex(ValueError, "different length policy"):
            news_jobs.validate_receipt(receipt, {**fixture.job(), "length_policy": 2})


if __name__ == "__main__":
    unittest.main()
