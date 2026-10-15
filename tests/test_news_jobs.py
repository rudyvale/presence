from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_news
import news_jobs
import test_auto_news


class NewsJobTests(unittest.TestCase):
    def setUp(self):
        fixture = test_auto_news.AutomatedNewsTests()
        fixture.setUp()
        self.report = fixture.report
        self.item = fixture.item
        self.researched = fixture.researched
        self.now = datetime(2026, 10, 14, 15, 30, tzinfo=timezone.utc)

    def job(self):
        return {"key": "news-0", "kind": "new", "record_route": "", "date": "2026-10-14", "sources": [news_jobs.source_input(self.item)]}

    def receipt(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"NEWS_JOB_JSON": json.dumps(self.job())}), patch.object(auto_news, "PROCESSING_DEADLINE", None), patch.object(auto_news, "check_generation_schema"), patch.object(auto_news, "prepare_report", return_value=(self.report, self.researched)), patch.object(auto_news, "notice"):
            news_jobs.worker(Path(directory))
            return json.loads((Path(directory) / "report.json").read_text())

    def test_parallel_publications_have_distinct_candidate_bundles(self):
        items = [{**self.item, "url": f"https://crypto.news/item-{index}/"} for index in range(6)]
        plan = news_jobs.make_plan(items, {"items": []}, self.now)
        self.assertEqual(len(plan["jobs"]), 2)
        first, second = plan["jobs"]
        self.assertFalse({item["url"] for item in first["sources"]} & {item["url"] for item in second["sources"]})

    def test_missing_sources_remain_an_explicit_failed_job_instead_of_false_success(self):
        plan = news_jobs.make_plan([], {"items": []}, self.now)
        self.assertEqual(plan["new_due"], 2)
        self.assertEqual(len(plan["jobs"]), 2)
        self.assertEqual(plan["jobs"][0]["sources"], [])

    def test_report_artifact_preserves_audit_without_redistributing_source_prose(self):
        receipt = self.receipt()
        news_jobs.validate_receipt(receipt, self.job())
        self.assertNotIn("facts", receipt["item"])
        self.assertNotIn("text", receipt["item"]["source"])
        self.assertEqual(receipt["item"]["fact_count"], 8)
        self.assertEqual(len(receipt["item"]["fact_hashes"]), 8)
        receipt["report"]["title"] = "Altered after validation"
        with self.assertRaisesRegex(ValueError, "integrity"):
            news_jobs.validate_receipt(receipt, self.job())

    def test_publisher_rechecks_daily_limit_before_applying_a_finished_worker(self):
        receipt = self.receipt()
        plan = {"created": self.now.isoformat(), "jobs": [self.job()]}
        history = {"items": [{"date": "2026-10-14", "source_url": "other-1"}, {"date": "2026-10-14", "source_url": "other-2"}]}
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "report.json").write_text(json.dumps(receipt))
            with patch.dict("os.environ", {"NEWS_PLAN_JSON": json.dumps(plan)}), patch.object(auto_news, "load_history", return_value=history), patch.object(auto_news, "publish_report") as publish, patch.object(auto_news, "notice"):
                news_jobs.apply_reports(Path(directory))
                publish.assert_not_called()

    def test_missing_worker_artifact_never_becomes_a_placeholder(self):
        plan = {"created": self.now.isoformat(), "jobs": [self.job()]}
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"NEWS_PLAN_JSON": json.dumps(plan)}), patch.object(auto_news, "publish_report") as publish, patch.object(auto_news, "notice"):
            with self.assertRaisesRegex(RuntimeError, "no complete report artifact"):
                news_jobs.apply_reports(Path(directory))
            publish.assert_not_called()

    def test_incompatible_artifact_does_not_discard_a_valid_independent_report(self):
        good = self.receipt()
        bad = {**good, "job_key": "news-1", "editorial_version": 0}
        bad["sha256"] = news_jobs.digest({key: value for key, value in bad.items() if key != "sha256"})
        plan = {"created": self.now.isoformat(), "jobs": [self.job(), {**self.job(), "key": "news-1"}]}
        with tempfile.TemporaryDirectory() as directory:
            for name, receipt in (("good", good), ("bad", bad)):
                folder = Path(directory) / name
                folder.mkdir()
                (folder / "report.json").write_text(json.dumps(receipt))
            with patch.dict("os.environ", {"NEWS_PLAN_JSON": json.dumps(plan)}), patch.object(auto_news, "load_history", return_value={"items": []}), patch.object(auto_news, "publish_report", return_value={"url": "/articles/accepted/"}) as publish, patch.object(auto_news, "notice"):
                with self.assertRaisesRegex(RuntimeError, "different validation version"):
                    news_jobs.apply_reports(Path(directory))
                publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
