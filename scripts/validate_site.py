#!/usr/bin/env python3
"""Static acceptance checks for the PRESENCE GitHub Pages build."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from PIL import Image
from site_routes import BASE_URL, ROOT, canonical_for, content_pages, is_article, legacy_path, route_for


def local_target(reference: str, page: Path = ROOT / "index.html") -> Path:
    clean = unquote(urlsplit(reference).path)
    target = (ROOT / clean.lstrip("/") if clean.startswith("/") else page.parent / clean).resolve()
    return target / "index.html" if target.is_dir() else target


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"src", "href"}:
                self.references.append(value)


def validate_catalog() -> list[str]:
    source = (ROOT / "assets/js/news-data.js").read_text(encoding="utf-8")
    match = re.fullmatch(r"\s*window\.PRESENCE_NEWS\s*=\s*(\[.*\]);?\s*", source, re.DOTALL)
    if not match:
        return ["news-data.js does not contain a JSON article array"]
    stories = sorted(
        json.loads(match[1]),
        key=lambda story: story["url"],
    )
    stories.sort(key=lambda story: story["date"], reverse=True)
    latest = [story for story in stories if story.get("promotable") is not False][:4]
    errors = []
    biographies = json.loads((ROOT / "assets/data/author-bios.json").read_text(encoding="utf-8"))["authors"]
    for story in stories:
        expected_authors = story["author"].split(" & ") if story.get("author") else []
        target = local_target(story["url"])
        if not target.is_file():
            errors.append(f"{story['url']}: catalog article does not exist")
            continue
        if not re.fullmatch(r"/articles/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*/", story["url"]):
            errors.append(f"{story['url']}: catalog article must use a clean route")
        if story.get("image") and not local_target(story["image"]).is_file():
            errors.append(f"{story['url']}: catalog image does not exist")
        document = target.read_text(encoding="utf-8")
        profile_authors = [
            unescape(name)
            for name in re.findall(r'class="author__bio"><strong>([^<]+)</strong>', document)
        ]
        if profile_authors != expected_authors:
            errors.append(f"{story['url']}: author profiles do not match the catalog")
        if any(name not in biographies for name in expected_authors):
            errors.append(f"{story['url']}: contributor biography is missing")
        for schema_text in re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', document, re.DOTALL):
            try:
                graph = json.loads(schema_text).get("@graph", [])
            except json.JSONDecodeError:
                continue
            for item in graph:
                if item.get("@type") != "Article":
                    continue
                if item.get("author", {}).get("name", "") != story.get("author", ""):
                    errors.append(f"{story['url']}: structured author does not match the catalog")
                if not expected_authors and "author" in item:
                    errors.append(f"{story['url']}: an unsigned article must not invent an author")
    for filename, slot, expected in (
        ("index.html", "LATEST-CARDS", latest),
        ("news/index.html", "NEWS-CARDS", stories),
    ):
        document = (ROOT / filename).read_text(encoding="utf-8")
        fragments = re.findall(
            rf'<template data-presence-slot="{slot}:START"></template>(.*?)<template data-presence-slot="{slot}:END"></template>',
            document,
            re.DOTALL,
        )
        if len(fragments) != 1:
            errors.append(f"{filename}: expected one {slot} slot")
            continue
        urls = re.findall(r'<h2><a href="([^"]+)">', fragments[0])
        dates = re.findall(r'<time\b[^>]*\bdatetime="([^"]+)"', fragments[0])
        if urls != [story["url"] for story in expected]:
            errors.append(f"{filename}: {slot} stories are missing, stale, or out of publication order")
        if dates != [story["date"] for story in expected]:
            errors.append(f"{filename}: {slot} publication dates do not match the catalog")
    feed = ET.parse(ROOT / "feed.xml")
    feed_links = [node.text for node in feed.findall("channel/item/link")]
    if set(feed_links) != {BASE_URL + story["url"] for story in stories} or len(feed_links) != len(stories):
        errors.append("RSS links do not match the clean catalog routes")
    return errors


def main() -> int:
    errors = validate_catalog()
    pages = content_pages()
    article_pages = [page for page in pages if is_article(page)]
    redirects = {legacy_path(page): page for page in pages if legacy_path(page) is not None}
    all_pages = set(ROOT.rglob("*.html"))
    if all_pages != set(pages) | set(redirects):
        errors.append("HTML files exist outside the clean routes and legacy redirects")
    expected_sitemap = {
        canonical_for(page)
        for page in pages
        if page.name != "404.html"
    }

    for page in pages:
        document = page.read_text(encoding="utf-8")
        relative = page.relative_to(ROOT).as_posix()
        if document.count('<link rel="canonical"') != 1:
            errors.append(f"{relative}: canonical count is not 1")
        if f'<link rel="canonical" href="{canonical_for(page)}">' not in document:
            errors.append(f"{relative}: canonical does not match the clean route")
        schemas = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', document, re.DOTALL)
        if len(schemas) != 1:
            errors.append(f"{relative}: JSON-LD count is not 1")
        else:
            try:
                json.loads(schemas[0])
            except json.JSONDecodeError as exc:
                errors.append(f"{relative}: invalid JSON-LD ({exc})")
        if document.count('class="nav-search-link"') != 1:
            errors.append(f"{relative}: search navigation link count is not 1")
        if is_article(page) and document.count("PRESENCE FOLLOW:START") != 1:
            errors.append(f"{relative}: article follow block count is not 1")

        parser = ReferenceParser()
        parser.feed(document)
        for reference in parser.references:
            parsed = urlsplit(reference)
            if reference.startswith("#"):
                continue
            if (parsed.scheme or parsed.netloc) and parsed.netloc != urlsplit(BASE_URL).netloc:
                continue
            clean = parsed.path
            if not clean:
                continue
            target = local_target(reference, page)
            try:
                target.relative_to(ROOT)
            except ValueError:
                errors.append(f"{relative}: reference escapes site root: {reference}")
                continue
            if not target.is_file():
                errors.append(f"{relative}: missing reference: {reference}")
            if clean.endswith(".html") and clean != "/404.html":
                errors.append(f"{relative}: internal link still uses .html: {reference}")

    for redirect, destination in redirects.items():
        if not redirect.is_file():
            errors.append(f"{redirect.relative_to(ROOT)}: missing legacy redirect")
            continue
        document = redirect.read_text(encoding="utf-8")
        route = route_for(destination)
        required = (
            f'data-presence-redirect="{route}"',
            f'<link rel="canonical" href="{BASE_URL}{route}">',
            f'<noscript><meta http-equiv="refresh" content="0; url={route}"></noscript>',
            f'<a href="{route}">',
            'src="/assets/js/redirect.js?v=',
        )
        if not all(value in document for value in required):
            errors.append(f"{redirect.relative_to(ROOT)}: incomplete or incorrect legacy redirect")

    site_text = "\n".join(page.read_text(encoding="utf-8") for page in pages)
    removed_mailbox = "contact" + "@" + "presence.media"
    if removed_mailbox in site_text or "mailto:" in site_text:
        errors.append("email address or mailto remains in HTML")

    sitemap = ET.parse(ROOT / "sitemap.xml")
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    actual_sitemap = {node.text or "" for node in sitemap.findall("sm:url/sm:loc", namespace)}
    if actual_sitemap != expected_sitemap or len(sitemap.findall("sm:url", namespace)) != len(expected_sitemap):
        errors.append(
            f"sitemap mismatch: expected {len(expected_sitemap)}, found {len(actual_sitemap)}"
        )

    ET.parse(ROOT / "feed.xml")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {BASE_URL}/sitemap.xml" not in robots:
        errors.append("robots.txt does not advertise the sitemap")

    for image_path in (ROOT / "assets" / "img").rglob("*.webp"):
        try:
            with Image.open(image_path) as image:
                image.verify()
        except Exception as exc:  # noqa: BLE001 - acceptance should report every decoder failure
            errors.append(f"{image_path.relative_to(ROOT).as_posix()}: invalid WebP ({exc})")

    checks = {
        "HTML pages": len(pages),
        "Article pages": len(article_pages),
        "Legacy redirects": len(redirects),
        "Sitemap URLs": len(actual_sitemap),
        "WebP assets": len(list((ROOT / "assets" / "img").rglob("*.webp"))),
        "Errors": len(errors),
    }
    for label, value in checks.items():
        print(f"{label}: {value}")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
