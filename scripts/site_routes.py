from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://presence.news"


def content_pages() -> list[Path]:
    return sorted([*ROOT.rglob("index.html"), ROOT / "404.html"])


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
