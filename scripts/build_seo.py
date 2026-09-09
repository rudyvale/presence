#!/usr/bin/env python3
"""Build repeatable SEO metadata and discovery files for the static site."""

from __future__ import annotations

from datetime import date
from html import escape, unescape
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from build_catalog import build_catalog, date_label, load_stories, publication_time
from site_routes import BASE_URL, ROOT, canonical_for, content_pages, is_article, legacy_path, route_for


SEO_START = "<!-- PRESENCE SEO:START -->"
SEO_END = "<!-- PRESENCE SEO:END -->"
FOLLOW_MARKER = "<!-- PRESENCE FOLLOW:START -->"


def clean_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def capture(pattern: str, document: str, default: str = "") -> str:
    match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
    return clean_text(match.group(1)) if match else default


def absolute_url(value: str, canonical: str) -> str:
    if value.startswith(("https://", "http://")):
        return value
    return urljoin(canonical, value)


def page_schema(path: Path, document: str, canonical: str, image: str, story: dict | None = None) -> dict:
    title = capture(r"<title>(.*?)</title>", document, "PRESENCE")
    description = capture(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        document,
        "Technology, power, and the ideas shaping what comes next.",
    )
    relative = path.relative_to(ROOT).as_posix()

    organization = {
        "@type": "Organization",
        "@id": f"{BASE_URL}/#organization",
        "name": "PRESENCE",
        "url": f"{BASE_URL}/",
        "logo": f"{BASE_URL}/assets/img/presence-social.png",
        "sameAs": ["https://t.me/presencemedia"],
    }

    if relative.startswith("articles/"):
        headline = capture(r'<h1[^>]*class="article__title"[^>]*>(.*?)</h1>', document, title.removesuffix(" — PRESENCE"))
        author = capture(r'<p[^>]*class="article__meta"[^>]*>(.*?)\s*·', document)
        published = capture(r'<time[^>]*datetime="([^"]+)"', document)
        if story and story.get("republishedDate"):
            published = story["date"]
        section = capture(r'<span[^>]*class="article__cat"[^>]*>(.*?)</span>', document)
        article = {
            "@type": "Article",
            "@id": f"{canonical}#article",
            "headline": headline,
            "description": description,
            "mainEntityOfPage": canonical,
            "image": [image],
            **({"author": {"@type": "Person", "name": author}} if author else {}),
            "publisher": {"@id": f"{BASE_URL}/#organization"},
        }
        if published:
            article["datePublished"] = published
        if story and story.get("republishedDate"):
            article["dateModified"] = story["republishedDate"]
        if section:
            article["articleSection"] = section
        return {"@context": "https://schema.org", "@graph": [organization, article]}

    page_type = {
        "news/index.html": "CollectionPage",
        "about/index.html": "AboutPage",
        "contact/index.html": "ContactPage",
    }.get(relative, "WebPage")
    webpage = {
        "@type": page_type,
        "@id": f"{canonical}#webpage",
        "url": canonical,
        "name": title,
        "description": description,
        "isPartOf": {"@id": f"{BASE_URL}/#website"},
        "about": {"@id": f"{BASE_URL}/#organization"},
    }
    website = {
        "@type": "WebSite",
        "@id": f"{BASE_URL}/#website",
        "url": f"{BASE_URL}/",
        "name": "PRESENCE",
        "publisher": {"@id": f"{BASE_URL}/#organization"},
    }
    return {"@context": "https://schema.org", "@graph": [organization, website, webpage]}


def add_search_link(document: str, path: Path) -> str:
    if 'class="nav-search-link"' in document:
        return document
    link = '      <a class="nav-search-link" href="/#search">Search</a>\n'
    return re.sub(
        r'(\s+<a href="/about/"(?: aria-current="page")?>About</a>)',
        f"\n{link}\\1",
        document,
        count=1,
    )


def add_article_follow(document: str) -> str:
    if FOLLOW_MARKER in document:
        return document
    follow = f'''\n    {FOLLOW_MARKER}
    <aside class="article-follow" aria-labelledby="follow-presence-title">
      <p class="article-follow__kicker">Follow PRESENCE</p>
      <h2 id="follow-presence-title">New stories, without the noise.</h2>
      <p>Get new PRESENCE stories in Telegram or follow the open RSS feed in your reader.</p>
      <div class="article-follow__actions">
        <a class="btn btn--grad" href="https://t.me/presencemedia" target="_blank" rel="noopener noreferrer">Join Telegram</a>
        <a class="btn btn--quiet" href="/feed.xml">Follow RSS</a>
      </div>
    </aside>
    <!-- PRESENCE FOLLOW:END -->
'''
    marker = '\n    <section class="authors"'
    if marker in document:
        return document.replace(marker, f"{follow}{marker}", 1)
    return document.replace("\n  </article>", f"{follow}\n  </article>", 1)


def update_republication(document: str, story: dict | None) -> str:
    if not story or not story.get("republishedDate"):
        return document
    byline = f"{escape(story['author'])} · " if story.get("author") else ""
    meta = f'<p class="article__meta">{byline}{publication_time(story)} · {escape(story["readingTime"])}</p>'
    original = f'<p class="article__edition">Originally published <time datetime="{story["date"]}">{date_label(story["date"])}</time>.</p>'
    document = re.sub(r'\n\s*<p class="article__edition">.*?</p>', "", document, flags=re.DOTALL)
    document, count = re.subn(r'<p class="article__meta">.*?</p>', lambda match: meta + "\n    " + original, document, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Missing article byline for {story['url']}")
    return document


def update_document(path: Path, story: dict | None = None) -> None:
    document = path.read_text(encoding="utf-8")
    document = re.sub(
        rf"\n?{re.escape(SEO_START)}.*?{re.escape(SEO_END)}\n?",
        "\n",
        document,
        flags=re.DOTALL,
    )
    document = add_search_link(document, path)
    if is_article(path):
        document = add_article_follow(document)
        document = update_republication(document, story)

    canonical = canonical_for(path)
    default_image = f"{BASE_URL}/assets/img/presence-social.png"

    og_image_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', document, re.IGNORECASE)
    og_image = absolute_url(og_image_match.group(1), canonical) if og_image_match else default_image

    document = re.sub(
        r'(<meta\s+property="og:image"\s+content=")([^"]+)(")',
        lambda match: f"{match.group(1)}{absolute_url(match.group(2), canonical)}{match.group(3)}",
        document,
        flags=re.IGNORECASE,
    )
    document = re.sub(
        r'(<meta\s+name="twitter:image"\s+content=")([^"]+)(")',
        lambda match: f"{match.group(1)}{absolute_url(match.group(2), canonical)}{match.group(3)}",
        document,
        flags=re.IGNORECASE,
    )
    document = re.sub(
        r'(<meta\s+name="twitter:card"\s+content=")[^"]+("\s*/?>)',
        r'\1summary_large_image\2',
        document,
        flags=re.IGNORECASE,
    )

    title = capture(r"<title>(.*?)</title>", document, "PRESENCE")
    description = capture(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        document,
        "Technology, power, and the ideas shaping what comes next.",
    )
    additions = [
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">',
        f'<meta property="og:url" content="{escape(canonical, quote=True)}">',
    ]
    if story and story.get("republishedDate"):
        additions.append(f'<meta property="article:modified_time" content="{story["republishedDate"]}">')
    if 'property="og:type"' not in document:
        additions.append(f'<meta property="og:type" content="{"article" if is_article(path) else "website"}">')
    if 'property="og:site_name"' not in document:
        additions.append('<meta property="og:site_name" content="PRESENCE">')
    if 'property="og:title"' not in document:
        additions.append(f'<meta property="og:title" content="{escape(title, quote=True)}">')
    if 'property="og:description"' not in document:
        additions.append(f'<meta property="og:description" content="{escape(description, quote=True)}">')
    if not og_image_match:
        additions.append(f'<meta property="og:image" content="{default_image}">')
    if 'name="twitter:card"' not in document:
        additions.append('<meta name="twitter:card" content="summary_large_image">')
    if 'name="twitter:title"' not in document:
        additions.append(f'<meta name="twitter:title" content="{escape(title, quote=True)}">')
    if 'name="twitter:description"' not in document:
        additions.append(f'<meta name="twitter:description" content="{escape(description, quote=True)}">')
    if 'name="twitter:image"' not in document:
        additions.append(f'<meta name="twitter:image" content="{og_image}">')

    schema = page_schema(path, document, canonical, og_image, story)
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2).replace("</", "<\\/")
    seo_block = f"{SEO_START}\n" + "\n".join(additions) + f'\n<script type="application/ld+json">\n{schema_json}\n</script>\n{SEO_END}\n'
    document = document.replace("</head>", f"{seo_block}</head>", 1)
    path.write_text(document, encoding="utf-8", newline="\n")


def write_sitemap(paths: list[Path], stories: dict[str, dict]) -> None:
    entries = []
    for path in paths:
        if path.name == "404.html":
            continue
        canonical = canonical_for(path)
        relative = path.relative_to(ROOT).as_posix()
        published = re.match(r"articles/(\d{4}-\d{2}-\d{2})_", relative)
        lastmod = published.group(1) if published else date.today().isoformat()
        lastmod = stories.get(route_for(path), {}).get("republishedDate") or lastmod
        entries.append(
            "  <url>\n"
            f"    <loc>{escape(canonical)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            "  </url>"
        )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(entries) + "\n</urlset>\n"
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n",
        encoding="utf-8",
        newline="\n",
    )


def update_feed() -> None:
    path = ROOT / "feed.xml"
    document = path.read_text(encoding="utf-8")
    document = document.replace(
        '<rss version="2.0">',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        1,
    )
    document = document.replace(
        "    <link>./index.html</link>",
        f"    <link>{BASE_URL}/</link>\n"
        f'    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml" />',
        1,
    )
    document = document.replace("<link>./articles/", f"<link>{BASE_URL}/articles/")
    document = re.sub(
        rf"(<link>{re.escape(BASE_URL)}/articles/[^<]+)\.html(</link>)",
        r"\1/\2",
        document,
    )
    path.write_text(document, encoding="utf-8", newline="\n")


def write_redirects(paths: list[Path]) -> list[Path]:
    redirects = []
    for path in paths:
        legacy = legacy_path(path)
        if legacy is None:
            continue
        target = escape(route_for(path), quote=True)
        canonical = escape(canonical_for(path), quote=True)
        document = f'''<!doctype html>
<html lang="en" data-presence-redirect="{target}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; script-src 'self'; object-src 'none'">
<title>Page moved — PRESENCE</title>
<link rel="canonical" href="{canonical}">
<script src="/assets/js/redirect.js?v=0"></script>
<noscript><meta http-equiv="refresh" content="0; url={target}"></noscript>
</head>
<body><p>This page has moved. <a href="{target}">Continue to PRESENCE</a>.</p></body>
</html>
'''
        legacy.write_text(document, encoding="utf-8", newline="\n")
        redirects.append(legacy)
    return redirects


def update_asset_versions(paths: list[Path]) -> None:
    assets = (
        "assets/css/site.css",
        "assets/css/about.css",
        "assets/css/fonts.css",
        "assets/js/site.js",
        "assets/js/news-data.js",
        "assets/js/news.js",
        "assets/js/contact.js",
        "assets/js/redirect.js",
    )
    versions = {
        asset: sha256((ROOT / asset).read_bytes()).hexdigest()[:16]
        for asset in assets
    }
    for path in paths:
        document = path.read_text(encoding="utf-8")
        for asset, version in versions.items():
            filename = asset.rsplit("/", 1)[-1]
            document = re.sub(
                rf'({re.escape(asset)})\?v=[a-f0-9]+',
                rf'\1?v={version}',
                document,
            )
            if filename not in document:
                continue
        path.write_text(document, encoding="utf-8", newline="\n")


def main() -> None:
    build_catalog()
    stories = {story["url"]: story for story in load_stories()}
    paths = content_pages()
    for path in paths:
        update_document(path, stories.get(route_for(path)))
    write_sitemap(paths, stories)
    update_feed()
    redirects = write_redirects(paths)
    update_asset_versions(paths + redirects)
    print(f"SEO updated for {len(paths)} HTML pages")
    print(f"Legacy redirects updated: {len(redirects)}")


if __name__ == "__main__":
    main()
