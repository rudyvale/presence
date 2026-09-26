from pathlib import Path
from datetime import date
import json
import re
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://presence.news"


def article_redirects() -> dict[str, str]:
    redirects = json.loads((ROOT / "assets/data/article-redirects.json").read_text(encoding="utf-8"))
    if not isinstance(redirects, dict):
        raise ValueError("Article redirects must be an object")
    for source, target in redirects.items():
        for route in (source, target):
            if not isinstance(route, str) or not re.fullmatch(r"/articles/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*/", route):
                raise ValueError(f"Invalid article redirect route: {route}")
            date.fromisoformat(route.split("/")[2][:10])
        if target in redirects:
            raise ValueError(f"Article redirect chains or loops are not allowed: {source}")
    return redirects


def content_pages() -> list[Path]:
    aliases = {ROOT / source.lstrip("/") / "index.html" for source in article_redirects()}
    return sorted([*(path for path in ROOT.rglob("index.html") if path not in aliases), ROOT / "404.html"])


def redirect_pages(paths: list[Path]) -> dict[Path, Path]:
    redirects = {legacy_path(path): path for path in paths if legacy_path(path) is not None}
    for source, target in article_redirects().items():
        destination = ROOT / target.lstrip("/") / "index.html"
        if destination not in paths:
            raise ValueError(f"Article redirect destination is not a content page: {target}")
        alias = ROOT / source.lstrip("/") / "index.html"
        redirects[alias] = destination
        redirects[legacy_path(alias)] = destination
    return redirects


def route_for(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if path.name == "index.html":
        relative = relative.removesuffix("index.html")
    return "/" + quote(relative, safe="/-_.")


def canonical_for(path: Path) -> str:
    return BASE_URL + route_for(path)


def is_article(path: Path) -> bool:
    return path.relative_to(ROOT).parts[0] == "articles"


def legacy_path(path: Path) -> Path | None:
    if path.name != "index.html" or path.parent == ROOT:
        return None
    return path.parent.with_suffix(".html")
