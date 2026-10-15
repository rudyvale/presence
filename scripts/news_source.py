from hashlib import sha256
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup

MAX_SOURCE_BYTES = 3 * 1024 * 1024


def canonical_source_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"crypto.news", "www.crypto.news"} or parsed.username or parsed.password or parsed.port:
        raise ValueError("Unexpected source URL")
    return urlunsplit(("https", "crypto.news", parsed.path, parsed.query if parsed.path == "/" else "", ""))


class SourceRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        canonical_source_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def clean_text(value: str) -> str:
    return " ".join(value.split())


def extract_article(data: bytes, url: str) -> dict:
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Source page exceeds the size limit")
    soup = BeautifulSoup(data, "html.parser")
    structured = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        pending = value if isinstance(value, list) else [value]
        while pending:
            node = pending.pop()
            if not isinstance(node, dict):
                continue
            pending.extend(node.get("@graph", []))
            if isinstance(node.get("articleBody"), str):
                structured.append(node["articleBody"])
    for node in soup.select("script, style, nav, header, footer, aside, form, button, noscript, iframe"):
        node.decompose()
    candidates = []
    selectors = (".post-detail__content", ".entry-content", ".article-content", ".article__content", ".post-content", "[itemprop=articleBody]", "article")
    for selector in selectors:
        for container in soup.select(selector):
            paragraphs = []
            for node in container.select("p, h2, h3"):
                excluded = False
                for parent in [node, *node.parents]:
                    if parent is container.parent:
                        break
                    labels = " ".join(parent.get("class", [])) + " " + (parent.get("id") or "")
                    if re.search(r"related|newsletter|advert|social|share-|author-|disclaimer|recommend|subscription|read-more|comment", labels, re.I):
                        excluded = True
                        break
                text = clean_text(node.get_text(" ", strip=True))
                if excluded or len(text.split()) < 5 or re.match(r"(?:read more|you might also|disclaimer|subscribe|follow us)\b", text, re.I):
                    continue
                if text not in paragraphs:
                    paragraphs.append(text)
            text = "\n\n".join(paragraphs)
            if len(text.split()) >= 180:
                candidates.append((selector, text))
        if candidates:
            break
    if not candidates and structured:
        text = max(structured, key=len)
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        if len(text.split()) >= 180:
            candidates.append(("json-ld", text))
    if not candidates:
        raise ValueError("Full article body unavailable; an RSS excerpt cannot replace it")
    selector, text = max(candidates, key=lambda candidate: len(candidate[1]))
    if len(text) > 28000:
        raise ValueError("Source is too long for a single news report")
    links = []
    for link in soup.select("article a[href], .post-detail__content a[href], .entry-content a[href]"):
        target = urljoin(url, link["href"])
        parsed = urlsplit(target)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and parsed.hostname not in {"crypto.news", "www.crypto.news", "twitter.com", "x.com", "t.me"}:
            target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            if target not in links:
                links.append(target)
    return {"text": text, "word_count": len(text.split()), "sha256": sha256(text.encode()).hexdigest(), "extractor": selector, "reference_urls": links[:12]}


def fetch_article(url: str) -> dict:
    url = canonical_source_url(url)
    request = Request(url, headers={"User-Agent": "PresenceNews/2.0 (+https://presence.news)", "Accept": "text/html"})
    with build_opener(SourceRedirects()).open(request, timeout=40) as response:
        canonical_source_url(response.url)
        data = response.read(MAX_SOURCE_BYTES + 1)
    return extract_article(data, url)
