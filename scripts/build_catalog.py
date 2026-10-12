#!/usr/bin/env python3
from datetime import date
from html import escape
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ("crypto", "technology", "companies")
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def listing_date(story: dict) -> str:
    return story.get("republishedDate") or story["date"]


def is_news(story: dict) -> bool:
    return story.get("type") == "NEWS"


def listing_stories(stories: list[dict], section: str) -> list[dict]:
    if section == "news":
        return [story for story in stories if is_news(story)]
    if section not in CATEGORIES:
        raise ValueError(f"Unknown section: {section}")
    return [story for story in stories if not is_news(story) and story["category"] == section]


def publication_time(story: dict, class_name: str = "") -> str:
    published = date.fromisoformat(listing_date(story))
    label = f"{MONTHS[published.month - 1]} {published.day}, {published.year}"
    attribute = f' class="{class_name}"' if class_name else ""
    return f'<time{attribute} datetime="{published.isoformat()}">{label}</time>'


def latest_card(story: dict) -> str:
    byline = f"{escape(story['author'])} · " if story.get("author") else ""
    return f'''            <article class="latest-row">
              <h2><a href="{escape(story['url'])}">{escape(story['title'])}</a></h2>
              <p class="story-author">{byline}{publication_time(story)} · {escape(story['readingTime'])}</p>
            </article>'''


def featured_card(story: dict) -> str:
    byline = f"{escape(story['author'])} · " if story.get("author") else ""
    summary = f'<p class="featured-row__summary">{escape(story["summary"])}</p>'
    image = story.get("image")
    image_class = " featured-row--with-image" if image else ""
    media = f'''<a class="featured-row__media" href="{escape(story['url'])}" aria-label="Read {escape(story['title'])}">
                <img src="{escape(image)}" alt="{escape(story.get('imageAlt', ''))}" width="1280" height="720" decoding="async" fetchpriority="high">
              </a>''' if image else summary
    card = f'''            <article class="featured-row{image_class}">
              <div class="featured-row__main">
                <h2><a href="{escape(story['url'])}">{escape(story['title'])}</a></h2>
                <p class="story-author">{byline}{publication_time(story)} · {escape(story['readingTime'])}</p>
                {summary if image else ''}
              </div>
              {media}
            </article>'''
    return "\n".join(line.rstrip() for line in card.splitlines() if line.strip())


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


def build_listing(stories: list[dict], section: str) -> None:
    path = ROOT / section / "index.html"
    selected = listing_stories(stories, section)
    pool = [story for story in stories if is_news(story) == (section == "news")]
    counts = {category: sum(story["category"] == category for story in pool) for category in CATEGORIES}
    counts["all"] = len(pool)
    replace_slot(path, "NEWS-CARDS", "\n\n".join(map(news_card, selected)), "        ")
    if section == "news":
        filters = [
            f'        <button class="news-filter" id="{category}" type="button" data-news-filter="{category}" aria-pressed="{str(category == "all").lower()}">{category.capitalize()} <span data-news-count="{category}">{counts[category]}</span></button>'
            for category in ("all", *CATEGORIES)
        ]
    else:
        filters = []
        for category in CATEGORIES:
            active_class = " is-active" if category == section else ""
            current = ' aria-current="page"' if category == section else ""
            filters.append(f'        <a class="news-filter{active_class}" href="/{category}/"{current}>{category.capitalize()} <span data-news-count="{category}">{counts[category]}</span></a>')
    replace_slot(path, "NEWS-FILTERS", "\n".join(filters), "        ")
    document = path.read_text(encoding="utf-8")
    document = re.sub(r'(data-news-count="([a-z]+)">)\d+', lambda match: match[1] + str(counts[match[2]]), document)
    document = re.sub(r'placeholder="Search \d+ (?:stories|articles|news stories)"', f'placeholder="Search {len(selected)} {"news stories" if section == "news" else "articles"}"', document)
    document = re.sub(r'(<p class="news-empty" id="news-empty")(?: hidden)?(>)', lambda match: match[1] + (" hidden" if selected else "") + match[2], document)
    path.write_text(document, encoding="utf-8", newline="\n")


def build_catalog() -> None:
    stories = sorted(load_stories(), key=lambda story: (-date.fromisoformat(listing_date(story)).toordinal(), story["url"]))
    for story in stories:
        if not story["url"].startswith(f"/articles/{listing_date(story)}_"):
            raise ValueError(f"Article route date must match its display date: {story['url']}")
    editorial = [story for story in stories if story.get("promotable") is not False]
    latest = editorial[:4]
    pinned = sorted(
        [story for story in editorial if isinstance(story.get("featuredRank"), int) and 1 <= story["featuredRank"] <= 100],
        key=lambda story: story["featuredRank"],
    )
    featured = (pinned + [story for story in editorial if story not in pinned])[:3]
    replace_slot(ROOT / "index.html", "FEATURED-CARDS", "\n".join(map(featured_card, featured)), "            ")
    replace_slot(ROOT / "index.html", "LATEST-CARDS", "\n".join(map(latest_card, latest)), "            ")
    for section in ("news", *CATEGORIES):
        build_listing(stories, section)
    print(f"Catalog listings updated: {len(featured)} featured, {len(latest)} latest, {sum(map(is_news, stories))} news stories, {sum(not is_news(story) for story in stories)} articles")


if __name__ == "__main__":
    build_catalog()
