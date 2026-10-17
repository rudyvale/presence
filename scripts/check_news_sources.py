import argparse
from hashlib import sha256

from bs4 import BeautifulSoup

from auto_news import body_text, load_history, notice
from build_catalog import ROOT, load_stories
from news_quality import validate_report
from news_source import fetch_article


def verify_source(record: dict, story: dict, document: str, source: dict) -> None:
    soup = BeautifulSoup(document, "html.parser")
    title = soup.select_one("h1.article__title")
    body = soup.select_one(".article__body")
    if title is None or body is None:
        raise ValueError("Published article structure is missing")
    report = {
        "title": title.get_text(" ", strip=True), "summary": story["summary"],
        "paragraphs": [node.get_text(" ", strip=True) for node in body.select(":scope > p")],
        "headings": [node.get_text(" ", strip=True) for node in body.select(":scope > h2")],
    }
    validate_report(report, {"title": record["source_snapshot"]["headline"], "source": source, "length_policy": record.get("length_policy", 0)})
    if sha256(body_text(document).encode()).hexdigest() != record["body_sha256"]:
        raise ValueError("Published body differs from its editorial audit")
    if len(" ".join(report["paragraphs"]).split()) != record["word_count"]:
        raise ValueError("Published word count differs from its editorial audit")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", action="append", default=[])
    args = parser.parse_args()
    records = [record for record in load_history()["items"] if record.get("format_version", 1) >= 3]
    if args.article:
        records = [record for record in records if record["article_url"] in args.article]
        if {record["article_url"] for record in records} != set(args.article):
            raise ValueError("A requested article has no complete source audit")
    else:
        records = records[-8:]
    if not records:
        raise ValueError("No complete reports are available for source verification")
    stories = {story["url"]: story for story in load_stories()}
    failures = []
    for record in records:
        try:
            document = (ROOT / record["article_url"].lstrip("/") / "index.html").read_text()
            source = fetch_article(record["source_url"])
            verify_source(record, stories[record["article_url"]], document, source)
            notice("Source verified", f"{record['article_url']}: {record['word_count']} words checked against {source['word_count']} source words; quantities, prose originality and audit hash match")
        except (ValueError, OSError, KeyError) as error:
            failures.append(f"{record['article_url']}: {error}")
            notice("Source check failed", failures[-1], error=True)
    if failures:
        raise RuntimeError(" | ".join(failures))
    notice("Editorial source checks", f"{len(records)} complete reports verified against fresh full source pages")


if __name__ == "__main__":
    main()
