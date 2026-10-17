import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time

import auto_news
from news_quality import editorial_issues, quantities, validate_completeness, validate_numbers, validate_report_structure
from news_source import canonical_source_url


def digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def output(name: str, value) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as destination:
            destination.write(name + "=" + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)) + "\n")


def source_input(item: dict) -> dict:
    return {"url": item["url"], "title": item["title"], "description": item.get("description", ""), "published": item["published"].isoformat()}


def make_plan(items: list[dict], history: dict, now: datetime) -> dict:
    jobs = []
    for index, record in enumerate(history["items"]):
        if not auto_news.needs_repair(record):
            continue
        snapshot = record.get("source_snapshot", {})
        source = {"url": record["source_url"], "title": snapshot.get("headline", "News update"), "description": "", "published": snapshot.get("published", record["date"] + "T12:00:00+00:00")}
        if constraints := record.get("requested_editorial_instructions") or record.get("editorial_revision"):
            source["editorial_constraints"] = constraints
        jobs.append({"key": f"repair-{index}", "kind": "repair", "record_route": record["article_url"], "date": record["date"], "length_policy": auto_news.LENGTH_POLICY, "previous_body_sha256": record.get("body_sha256"), "sources": [source]})
    today = now.astimezone(auto_news.MOSCOW).date().isoformat()
    count = sum(record["date"] == today for record in history["items"])
    deficit = max(0, min(auto_news.DAILY_LIMIT, auto_news.due_count(now)) - count)
    candidates = auto_news.eligible_items(items, history, now)
    for slot in range(deficit):
        bundle = candidates[slot * 3:(slot + 1) * 3]
        jobs.append({"key": f"news-{slot}", "kind": "new", "record_route": "", "date": today, "length_policy": auto_news.LENGTH_POLICY, "sources": [source_input(item) for item in bundle]})
    return {"version": 2, "created": now.isoformat(), "jobs": jobs, "new_due": deficit}


def plan() -> None:
    now = datetime.now(timezone.utc)
    items = auto_news.fetch_feed(now)
    data = make_plan(items, auto_news.load_history(), now)
    output("jobs", data["jobs"])
    output("plan", data)
    output("ready", "true" if data["jobs"] else "false")
    auto_news.notice("Editorial plan", f"{len(data['jobs'])} independent report jobs; {data['new_due']} new publication slots due; {len(items)} recent sources")


def worker(destination: Path) -> None:
    job = json.loads(os.environ["NEWS_JOB_JSON"])
    if not re.fullmatch(r"(?:repair|news)-\d+", job["key"]) or job["kind"] not in {"repair", "new"}:
        raise ValueError("Invalid editorial job")
    auto_news.PROCESSING_DEADLINE = time.monotonic() + 60 * 60
    auto_news.check_generation_schema()
    failures = []
    for source in job["sources"]:
        try:
            item = {**source, "url": canonical_source_url(source["url"]), "published": datetime.fromisoformat(source["published"])}
            report, researched = auto_news.prepare_report(item)
            facts = researched["facts"]
            evidence = researched["title"] + " " + researched["source"]["text"]
            receipt = {
                "version": 2, "job_key": job["key"], "kind": job["kind"], "record_route": job["record_route"], "date": job["date"], "report": report,
                "editorial_version": auto_news.FORMAT_VERSION,
                "item": {
                    "length_policy": researched.get("length_policy", 0),
                    "url": item["url"], "title": item["title"], "published": item["published"].isoformat(),
                    "fact_count": len(facts), "fact_hashes": [sha256(fact.encode()).hexdigest() for fact in facts],
                    "source": {key: researched["source"][key] for key in ("word_count", "sha256", "extractor", "reference_urls")},
                },
            }
            receipt["item"]["source"]["quantities"] = sorted(quantities(evidence))
            receipt["sha256"] = digest(receipt)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "report.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            auto_news.notice("Report ready", f"{job['key']}: {len(' '.join(report['paragraphs']).split())} words; {len(facts)} facts; source {researched['source']['word_count']} words; factual and originality checks passed")
            return
        except (ValueError, OSError, RuntimeError) as error:
            failures.append(f"{source['url']}: {type(error).__name__}: {error}")
            auto_news.notice("Candidate rejected", failures[-1])
    raise RuntimeError(" | ".join(failures) or "No source was available")


def validate_receipt(receipt: dict, job: dict) -> None:
    saved = receipt.get("sha256")
    content = {key: value for key, value in receipt.items() if key != "sha256"}
    if saved != digest(content) or receipt.get("version") != 2:
        raise ValueError("Editorial artifact integrity check failed")
    if receipt.get("editorial_version") != auto_news.FORMAT_VERSION:
        raise ValueError("Editorial artifact was produced by a different validation version")
    if any(receipt.get(key) != job[key] for key in ("kind", "record_route", "date")) or receipt.get("job_key") != job["key"]:
        raise ValueError("Editorial artifact differs from its approved plan")
    item = receipt["item"]
    policy = item.get("length_policy", 0)
    if type(policy) is not int or policy not in {0, 1, 2}:
        raise ValueError("Unsupported report length policy")
    if "length_policy" in job and policy != job["length_policy"]:
        raise ValueError("Editorial artifact uses a different length policy than its approved plan")
    canonical_source_url(item["url"])
    if item["url"] not in {source["url"] for source in job["sources"]}:
        raise ValueError("Unexpected source in editorial artifact")
    minimum_facts, maximum_facts = (4, 100) if policy >= 2 else (7, 16)
    if not minimum_facts <= item["fact_count"] <= maximum_facts or len(item["fact_hashes"]) != item["fact_count"]:
        raise ValueError("Invalid research audit")
    if item["source"]["word_count"] < 180 or not re.fullmatch(r"[a-f0-9]{64}", item["source"]["sha256"]):
        raise ValueError("A full source page was not verified")
    text = validate_report_structure(receipt["report"])
    if issues := editorial_issues(text, policy >= 1):
        raise ValueError("; ".join(issues))
    if policy >= 1:
        validate_completeness(receipt["report"], item["source"]["word_count"], policy)
    validate_numbers(text, text)
    if quantities(text) - {tuple(value) for value in item["source"]["quantities"]}:
        raise ValueError("Report quantities differ from the verified source")


def apply_reports(directory: Path) -> None:
    plan_data = json.loads(os.environ["NEWS_PLAN_JSON"])
    jobs = {job["key"]: job for job in plan_data["jobs"]}
    receipts = {}
    failures = []
    rejected = set()
    for path in directory.glob("**/report.json"):
        receipt = json.loads(path.read_text())
        key = receipt.get("job_key")
        if key not in jobs or key in receipts:
            raise ValueError("Unexpected or duplicate editorial artifact")
        try:
            validate_receipt(receipt, jobs[key])
        except (ValueError, KeyError, TypeError) as error:
            failures.append(f"{key}: {error}")
            rejected.add(key)
            continue
        receipts[key] = receipt
    changed = []
    for key, job in jobs.items():
        if key not in receipts:
            if key not in rejected:
                failures.append(key + ": no complete report artifact")
            continue
        receipt = receipts[key]
        history = auto_news.load_history()
        item = {**receipt["item"], "published": datetime.fromisoformat(receipt["item"]["published"])}
        record = None
        if job["kind"] == "repair":
            record = next((entry for entry in history["items"] if entry["article_url"] == job["record_route"]), None)
            if record is None:
                failures.append(key + ": original report no longer exists")
                continue
            if not auto_news.needs_repair(record):
                continue
            if job.get("previous_body_sha256") != record.get("body_sha256"):
                failures.append(key + ": article changed after the repair was planned")
                continue
        else:
            count = sum(entry["date"] == job["date"] for entry in history["items"])
            if count >= auto_news.DAILY_LIMIT or any(entry["source_url"] == item["url"] for entry in history["items"]):
                continue
        now = datetime.fromisoformat(plan_data["created"])
        story = auto_news.publish_report(item, receipt["report"], now, record)
        changed.append(story["url"])
    output("articles", changed)
    output("changed", "true" if changed else "false")
    auto_news.notice("Publication result", f"{len(changed)} complete reports applied; {len(failures)} jobs incomplete")
    if failures:
        raise RuntimeError(" | ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "worker", "apply"])
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "worker":
        worker(args.directory)
    else:
        apply_reports(args.directory)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        auto_news.notice("Editorial job failed", f"{type(error).__name__}: {error}", error=True)
        raise SystemExit(1)
