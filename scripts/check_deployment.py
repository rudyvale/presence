import os
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from site_routes import BASE_URL, ROOT


def check_route(route: str, expected_status: int) -> None:
    query = urlencode({"deployment": os.environ.get("GITHUB_SHA", "check")})
    request = Request(BASE_URL + route + "?" + query, headers={"User-Agent": "PresenceDeploymentCheck/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    if status != expected_status:
        raise RuntimeError(f"{route}: expected HTTP {expected_status}, received HTTP {status}")


def main() -> None:
    article = os.environ.get("EXPECTED_ARTICLE", "")
    if not article:
        history_path = ROOT / "docs/editorial/auto-news-history.json"
        if history_path.exists():
            history = json.loads(history_path.read_text())
            if history["items"]:
                article = history["items"][-1]["article_url"]
    public_routes = ["/", "/news/"]
    if article:
        if not article.startswith("/articles/") or not article.endswith("/") or any(character in article for character in "?#"):
            raise ValueError("Invalid publication route")
        public_routes.append(article)
    private_routes = ["/scripts/auto_news.py", "/tests/test_auto_news.py", "/docs/editorial/automated-news.md", "/README.md", "/README.html"]
    for attempt in range(24):
        try:
            for route in public_routes:
                check_route(route, 200)
            for route in private_routes:
                check_route(route, 404)
            print("::notice title=Public deployment::Pages serve the news and published article; automation code and editorial records return HTTP 404.")
            return
        except (OSError, RuntimeError) as error:
            if attempt == 23:
                raise
            print(f"Waiting for Pages propagation: {error}")
            time.sleep(5)


if __name__ == "__main__":
    main()
