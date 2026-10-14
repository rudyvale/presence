#!/usr/bin/env python3
"""Import an editorial manuscript into the static site's news catalog."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from html import escape
import json
import math
from pathlib import Path
import re

from build_catalog import CATEGORIES, MONTHS, ROOT, load_stories


def parse_manuscript(text: str) -> tuple[str, list[str], str]:
    sections = re.split(r"(?im)^Sources for editorial verification:?\s*$", text, maxsplit=1)
    article = sections[0]
    notes = sections[1].strip() if len(sections) == 2 else ""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", article.strip()) if part.strip()]
    if len(paragraphs) < 3:
        raise ValueError("A manuscript needs a title, introduction and article body")
    title = paragraphs[0].removeprefix("# ").strip()
    if "\n" in title or len(title) > 300:
        raise ValueError("The title must be a single line of at most 300 characters")
    if len(paragraphs) > 2:
        try:
            datetime.strptime(paragraphs[2], "%B %d, %Y")
        except ValueError:
            pass
        else:
            paragraphs.pop(2)
    if len(paragraphs) < 3:
        raise ValueError("The dateline cannot replace the article body")
    return title, paragraphs[1:], ("Sources for editorial verification:\n" + notes) if notes else ""


def hero_markup(image: str, image_alt: str) -> str:
    from PIL import Image
    if not re.fullmatch(r"/assets/img/articles/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*\.(?:png|jpe?g|webp)", image):
        raise ValueError("Use a local article image under /assets/img/articles/")
    with Image.open(ROOT / image.lstrip("/")) as asset:
        width, height = asset.size
        asset.verify()
    return f'''    <figure class="article__hero-media">
      <img src="{escape(image, quote=True)}" alt="{escape(image_alt, quote=True)}" width="{width}" height="{height}" decoding="async" fetchpriority="high">
    </figure>'''


def inline_markdown(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)


def render_body(paragraphs: list[str]) -> str:
    blocks = []
    for index, paragraph in enumerate(paragraphs):
        heading = paragraph.startswith("## ") or (
            index > 0 and "\n" not in paragraph and len(paragraph) <= 110
            and paragraph[-1] not in ".?!:;\u201d\""
        )
        if heading:
            blocks.append(f"      <h2>{inline_markdown(paragraph.removeprefix('## '))}</h2>")
        else:
            attribute = ' class="article__lede"' if index == 0 else ""
            blocks.append(f"      <p{attribute}>{inline_markdown(paragraph)}</p>")
    return "\n".join(blocks)


def import_news(source: Path, published: date, slug: str, summary: str, category: str = "crypto", image: str | None = None, image_alt: str = "") -> dict:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Use a lowercase, hyphenated slug")
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")
    if not summary.strip() or summary != summary.strip() or len(summary) > 1200 or any(ord(char) < 32 for char in summary):
        raise ValueError("Supply a plain-text catalog summary of at most 1200 characters")
    title, paragraphs, notes = parse_manuscript(source.read_text(encoding="utf-8-sig"))
    route = f"/articles/{published.isoformat()}_{slug}/"
    target = ROOT / route.lstrip("/") / "index.html"
    stories = load_stories()
    if target.exists() or any(story["url"] == route for story in stories):
        raise ValueError(f"Refusing to overwrite an existing article: {route}")

    reading_time = f"{math.ceil(len(' '.join(paragraphs).split()) / 220)} min read"
    story = dict(category=category, type="NEWS", title=title, summary=summary,
                 author="Presence Editorial", date=published.isoformat(),
                 readingTime=reading_time, url=route, promotable=True)
    hero = hero_markup(image, image_alt or title) if image else ""
    if image:
        story.update(image=image, imageAlt=image_alt or title)
    biography = json.loads((ROOT / "assets/data/author-bios.json").read_text(encoding="utf-8"))["authors"]["Presence Editorial"]["bio"]
    author = "Presence Editorial"
    biography_html = f"<strong>{author}</strong>" + escape(biography.removeprefix(author))
    substitutions = {
        "TITLE": escape(title), "SUMMARY": escape(summary, quote=True),
        "CATEGORY": category.capitalize(), "DATE": published.isoformat(),
        "DATE_LABEL": f"{MONTHS[published.month - 1]} {published.day}, {published.year}",
        "READING_TIME": reading_time, "BODY": render_body(paragraphs), "BIO": biography_html, "HERO": hero,
    }
    template = (ROOT / "scripts/templates/news-article.html.tmpl").read_text(encoding="utf-8")
    document = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: substitutions[match[1]], template)
    if re.search(r"\{\{[A-Z_]+\}\}", document):
        raise ValueError("An unresolved template field remains")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8", newline="\n")
    stories.insert(0, story)
    (ROOT / "assets/js/news-data.js").write_text("window.PRESENCE_NEWS = " + json.dumps(stories, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    if notes:
        folder = ROOT / "docs/editorial"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{published.isoformat()}_{slug}.md").write_text(f"# {title}\n\n{notes}\n", encoding="utf-8")
    return story


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--category", choices=CATEGORIES, default="crypto")
    parser.add_argument("--image", help="Local site image URL under /assets/img/articles/")
    parser.add_argument("--image-alt", default="")
    args = parser.parse_args()
    story = import_news(args.source, args.date, args.slug, args.summary, args.category, args.image, args.image_alt)
    from build_seo import main as build_site
    build_site()
    print(f"News imported: {story['url']}")


if __name__ == "__main__":
    main()
