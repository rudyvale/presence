#!/usr/bin/env python3
from datetime import date
from html import escape
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def listing_date(story: dict) -> str:
    return story.get("republishedDate") or story["date"]


def date_label(value: str) -> str:
    published = date.fromisoformat(value)
    return f"{MONTHS[published.month - 1]} {published.day}, {published.year}"


def publication_time(story: dict, class_name: str = "") -> str:
    published = date.fromisoformat(listing_date(story))
    label = f"{MONTHS[published.month - 1]} {published.day}, {published.year}"
    if story.get("republishedDate"):
        label = f"Republished {label}"
    attribute = f' class="{class_name}"' if class_name else ""
    return f'<time{attribute} datetime="{published.isoformat()}">{label}</time>'


def latest_card(story: dict) -> str:
    byline = f"{escape(story['author'])} · " if story.get("author") else ""
    return f'''            <article class="latest-row">
              <h2><a href="{escape(story['url'])}">{escape(story['title'])}</a></h2>
              <p class="story-author">{byline}{publication_time(story)} · {escape(story['readingTime'])}</p>
            </article>'''


def news_card(story: dict) -> str:
    category = escape(story["category"])
    byline = f"\n            <span>{escape(story['author'])}</span>" if story.get("author") else ""
    media = ""
    image_class = ""
    if story.get("image"):
        image_class = " news-card--with-image"
        media = f'''
          <a class="news-card__media" href="{escape(story['url'])}" aria-label="Read {escape(story['title'])}">
            <img src="{escape(story['image'])}" alt="{escape(story.get('imageAlt', ''))}" width="1280" height="720" decoding="async" loading="lazy">
          </a>'''
    return f'''        <article class="news-card news-card--{category}{image_class}">{media}
          <div class="news-card__meta">
            <span class="news-card__category">{category.capitalize()}</span>
            <span class="news-card__type">{escape(story['type'])}</span>
            {publication_time(story, 'news-card__date')}
          </div>
          <h2><a href="{escape(story['url'])}">{escape(story['title'])}</a></h2>
          <p class="news-card__summary">{escape(story['summary'])}</p>
          <div class="news-card__foot">{byline}
            <span>{escape(story['readingTime'])}</span>
          </div>
        </article>'''


def replace_slot(path: Path, slot: str, content: str, indent: str) -> None:
    document = path.read_text(encoding="utf-8")
    pattern = rf'(<template data-presence-slot="{slot}:START"></template>).*?(<template data-presence-slot="{slot}:END"></template>)'
    document, count = re.subn(
        pattern,
        lambda match: f"{match[1]}\n{content}\n{indent}{match[2]}",
        document,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError(f"Expected one {slot} slot in {path.name}, found {count}")
    path.write_text(document, encoding="utf-8", newline="\n")


def load_stories() -> list[dict]:
    source = (ROOT / "assets/js/news-data.js").read_text(encoding="utf-8")
    match = re.fullmatch(r"\s*window\.PRESENCE_NEWS\s*=\s*(\[.*\]);?\s*", source, re.DOTALL)
    if not match:
        raise ValueError("news-data.js must contain a JSON article array")
    return json.loads(match[1])


def build_catalog() -> None:
    stories = sorted(load_stories(), key=lambda story: (-date.fromisoformat(listing_date(story)).toordinal(), story["url"]))
    latest = [story for story in stories if story.get("promotable") is not False][:4]
    replace_slot(ROOT / "index.html", "LATEST-CARDS", "\n".join(map(latest_card, latest)), "            ")
    replace_slot(ROOT / "news/index.html", "NEWS-CARDS", "\n\n".join(map(news_card, stories)), "        ")
    print(f"Catalog listings updated: {len(latest)} latest, {len(stories)} news stories")


if __name__ == "__main__":
    build_catalog()
