from hashlib import sha256
from io import BytesIO
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image

from site_routes import BASE_URL, ROOT


def check_route(route: str, expected_status: int) -> bytes:
    query = urlencode({"deployment": os.environ.get("GITHUB_SHA", "check")})
    request = Request(BASE_URL + route + "?" + query, headers={"User-Agent": "PresenceDeploymentCheck/2.0"})
    data = b""
    try:
        with urlopen(request, timeout=25) as response:
            status = response.status
            if status == expected_status == 200:
                data = response.read(3 * 1024 * 1024)
    except HTTPError as error:
        status = error.code
    if status != expected_status:
        raise RuntimeError(f"{route}: expected HTTP {expected_status}, received HTTP {status}")
    return data


def verify_report(document: bytes, record: dict) -> str:
    soup = BeautifulSoup(document, "html.parser")
    body = soup.select_one(".article__body")
    hero = soup.select_one(".article__hero-media img")
    title = soup.select_one("h1")
    if not body or not hero or not title or len(body.get_text(" ", strip=True).split()) < 220:
        raise RuntimeError("Published report is truncated or has no illustration")
    text = body.get_text(" ", strip=True)
    if sha256(text.encode()).hexdigest() != record["body_sha256"]:
        raise RuntimeError("Published article differs from the validated editorial output")
    if len(body.select("h2")) != 2 or hero.get("src") != record["image"]:
        raise RuntimeError("Published sections or illustration do not match")
    image = hero["src"]
    if not re.fullmatch(r"/assets/img/articles/[a-z0-9_-]+/illustration-[a-f0-9]+\.webp", image):
        raise RuntimeError("Unexpected illustration path")
    return image


def main() -> None:
    history_path = ROOT / "docs/editorial/auto-news-history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {"items": []}
    records = {record["article_url"]: record for record in history["items"] if record.get("format_version") == 2}
    requested = json.loads(os.environ.get("EXPECTED_ARTICLES_JSON") or "[]")
    if not isinstance(requested, list) or any(not isinstance(route, str) for route in requested):
        raise ValueError("Invalid publication list")
    if not requested:
        requested = list(records)[-4:]
    for route in requested:
        if not re.fullmatch(r"/articles/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*/", route) or route not in records:
            raise ValueError("Expected publication has no complete editorial record")
    private_routes = ["/scripts/auto_news.py", "/tests/test_auto_news.py", "/docs/editorial/automated-news.md", "/docs/editorial/auto-news-history.json", "/README.md", "/README.html"]
    for attempt in range(24):
        try:
            check_route("/", 200)
            news = check_route("/news/", 200).decode("utf-8")
            for route in requested:
                if route not in news:
                    raise RuntimeError("A published report is missing from the news listing")
                image = verify_report(check_route(route, 200), records[route])
                image_data = check_route(image, 200)
                with Image.open(BytesIO(image_data)) as asset:
                    if asset.width < 1200 or asset.height < 675:
                        raise RuntimeError("Published illustration is too small")
                    asset.verify()
                local = BeautifulSoup((ROOT / route.lstrip("/") / "index.html").read_text(), "html.parser")
                remote = BeautifulSoup(check_route(route, 200), "html.parser")
                if local.h1.get_text() != remote.h1.get_text():
                    raise RuntimeError("Published headline does not match the deployed revision")
            for route in private_routes:
                check_route(route, 404)
            print(f"::notice title=Public deployment::{len(requested)} complete reports verified with exact body hashes, sections, news cards and working illustrations. Editorial code and records return HTTP 404.")
            return
        except (OSError, RuntimeError) as error:
            if attempt == 23:
                raise
            print(f"Waiting for Pages propagation: {error}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
