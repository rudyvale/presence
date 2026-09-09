#!/usr/bin/env python3
"""Build repeatable SEO metadata and discovery files for the static site."""

from __future__ import annotations

from datetime import date
from html import escape, unescape
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import quote, urljoin

from build_catalog import build_catalog


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://presence.news"
SEO_START = "<!-- PRESENCE SEO:START -->"
SEO_END = "<!-- PRESENCE SEO:END -->"
FOLLOW_MARKER = "<!-- PRESENCE FOLLOW:START -->"


def clean_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def capture(pattern: str, document: str, default: str = "") -> str:
    match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
    return clean_text(match.group(1)) if match else default


def canonical_for(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if relative == "index.html":
        return f"{BASE_URL}/"
    return f"{BASE_URL}/{quote(relative, safe='/-_.')}"


def absolute_url(value: str, canonical: str) -> str:
    if value.startswith(("https://", "http://")):
        return value
    return urljoin(canonical, value)


def page_schema(path: Path, document: str, canonical: str, image: str) -> dict:
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
        if section:
            article["articleSection"] = section
        return {"@context": "https://schema.org", "@graph": [organization, article]}

    page_type = {
        "news.html": "CollectionPage",
        "about.html": "AboutPage",
        "contact.html": "ContactPage",
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
    prefix = "../" if path.parent.name == "articles" else ""
    link = f'      <a class="nav-search-link" href="{prefix}index.html#future-archive">Search</a>\n'
    return re.sub(
        r'(\s+<a href="(?:\.\./)?about\.html"(?: aria-current="page")?>About</a>)',
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
        <a class="btn btn--quiet" href="../feed.xml">Follow RSS</a>
      </div>
    </aside>
    <!-- PRESENCE FOLLOW:END -->
'''
    marker = '\n    <section class="authors"'
    if marker in document:
        return document.replace(marker, f"{follow}{marker}", 1)
    return document.replace("\n  </article>", f"{follow}\n  </article>", 1)


def update_document(path: Path) -> None:
    document = path.read_text(encoding="utf-8")
    document = re.sub(
        rf"\n?{re.escape(SEO_START)}.*?{re.escape(SEO_END)}\n?",
        "\n",
        document,
        flags=re.DOTALL,
    )
    document = add_search_link(document, path)
    if path.parent.name == "articles":
        document = add_article_follow(document)

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
    is_article = path.parent.name == "articles"
    additions = [
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">',
        f'<meta property="og:url" content="{escape(canonical, quote=True)}">',
    ]
    if 'property="og:type"' not in document:
        additions.append(f'<meta property="og:type" content="{"article" if is_article else "website"}">')
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

    schema = page_schema(path, document, canonical, og_image)
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2).replace("</", "<\\/")
    seo_block = f"{SEO_START}\n" + "\n".join(additions) + f'\n<script type="application/ld+json">\n{schema_json}\n</script>\n{SEO_END}\n'
    document = document.replace("</head>", f"{seo_block}</head>", 1)
    path.write_text(document, encoding="utf-8", newline="\n")


def write_sitemap(paths: list[Path]) -> None:
    entries = []
    for path in paths:
        if path.name == "404.html":
            continue
        canonical = canonical_for(path)
        relative = path.relative_to(ROOT).as_posix()
        published = re.match(r"articles/(\d{4}-\d{2}-\d{2})_", relative)
        lastmod = published.group(1) if published else date.today().isoformat()
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
    path.write_text(document, encoding="utf-8", newline="\n")


def update_asset_versions(paths: list[Path]) -> None:
    assets = (
        "assets/css/site.css",
        "assets/css/about.css",
        "assets/css/fonts.css",
        "assets/js/site.js",
        "assets/js/news-data.js",
        "assets/js/news.js",
        "assets/js/contact.js",
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
                rf'((?:\.\./)?{re.escape(asset)})\?v=[a-f0-9]+',
                rf'\1?v={version}',
                document,
            )
            if filename not in document:
                continue
        path.write_text(document, encoding="utf-8", newline="\n")


def main() -> None:
    build_catalog()
    paths = sorted(ROOT.rglob("*.html"))
    for path in paths:
        update_document(path)
    write_sitemap(paths)
    update_feed()
    update_asset_versions(paths)
    print(f"SEO updated for {len(paths)} HTML pages")


if __name__ == "__main__":
    main()
