#!/usr/bin/env python3
"""Export only public site files, excluding Git metadata and editorial tooling."""
from pathlib import Path
import shutil
import sys

from site_routes import ROOT, content_pages, redirect_pages


def export_site(destination: Path) -> None:
    destination = destination.resolve()
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Export outside the repository")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Refusing to overwrite a nonempty export directory")
    destination.mkdir(parents=True, exist_ok=True)
    pages = content_pages()
    for source in [*pages, *redirect_pages(pages), *(ROOT / name for name in ("feed.xml", "sitemap.xml", "robots.txt", "CNAME", ".nojekyll"))]:
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copytree(ROOT / "assets", destination / "assets")


if __name__ == "__main__":
    export_site(Path(sys.argv[1]))
