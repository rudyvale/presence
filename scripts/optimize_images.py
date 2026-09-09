#!/usr/bin/env python3
"""Create efficient WebP variants and switch rendered images to them."""

from __future__ import annotations

from pathlib import Path
import re
import time

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IMAGE_TAG = re.compile(r'<img\b[^>]*\bsrc="[^"]+"[^>]*>', re.IGNORECASE)
SRC = re.compile(r'\bsrc="([^"]+)"', re.IGNORECASE)
MAX_EDGE = 1920


def write_document(path: Path, value: str) -> None:
    temporary = path.with_name(f"{path.name}.codex-tmp")
    for attempt in range(5):
        try:
            temporary.write_text(value, encoding="utf-8", newline="\n")
            os.replace(temporary, path)
            return
        except OSError:
            temporary.unlink(missing_ok=True)
            if attempt == 4:
                raise
            time.sleep(0.15 * (attempt + 1))


def convert(source: Path) -> Path:
    target = source.with_suffix(".webp")
    if target.exists() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return target

    with Image.open(source) as image:
        image.load()
        if source.name == "presence-logo.png":
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            image.save(target, "WEBP", lossless=True, method=6)
            return target

        if max(image.size) > MAX_EDGE:
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
        if has_alpha:
            image.save(target, "WEBP", quality=88, method=6, exact=True)
        else:
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(target, "WEBP", quality=84, method=6, optimize=True)
    return target


def update_tag(tag: str, document_path: Path, converted: dict[str, str]) -> str:
    match = SRC.search(tag)
    if not match:
        return tag
    value = match.group(1)
    if value.startswith(("http://", "https://", "data:")) or not re.search(r"\.(?:png|jpe?g)$", value, re.IGNORECASE):
        return tag
    source = (ROOT / value.lstrip("/") if value.startswith("/") else document_path.parent / value).resolve()
    try:
        source.relative_to(ROOT)
    except ValueError:
        return tag
    if not source.exists() or source.name == "presence-social.png":
        return tag

    target = convert(source)
    target_value = "/" + target.relative_to(ROOT).as_posix()
    converted[source.relative_to(ROOT).as_posix()] = target.relative_to(ROOT).as_posix()
    tag = tag[: match.start(1)] + target_value + tag[match.end(1) :]

    if "decoding=" not in tag:
        tag = tag[:-1] + ' decoding="async">'
    if "loading=" not in tag and "brand__mark" not in tag and "fetchpriority=" not in tag:
        tag = tag[:-1] + ' loading="lazy">'
    return tag


def main() -> None:
    converted: dict[str, str] = {}
    for target in (ROOT / "assets" / "img").rglob("*.webp"):
        for suffix in (".png", ".jpg", ".jpeg"):
            source = target.with_suffix(suffix)
            if source.exists():
                converted[source.relative_to(ROOT).as_posix()] = target.relative_to(ROOT).as_posix()
                break
    html_paths = sorted(ROOT.rglob("*.html"))
    for path in html_paths:
        document = path.read_text(encoding="utf-8")
        updated = IMAGE_TAG.sub(lambda match: update_tag(match.group(0), path, converted), document)
        if updated != document:
            write_document(path, updated)

    for relative in ("assets/js/news-data.js", "assets/data/future-catalog.json"):
        path = ROOT / relative
        if not path.exists():
            continue
        document = path.read_text(encoding="utf-8")
        for source, target in converted.items():
            document = document.replace(source, target)
        path.write_text(document, encoding="utf-8", newline="\n")

    social = ROOT / "assets" / "img" / "presence-social.png"
    favicon = ROOT / "assets" / "img" / "presence-icon.png"
    with Image.open(social) as icon:
        icon.load()
        icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
        icon.save(favicon, "PNG", optimize=True)
    for path in html_paths:
        document = path.read_text(encoding="utf-8")
        updated = re.sub(
            r'(<link\s+rel="icon"\s+href="/assets/img/)presence-social\.png("\s+type="image/png">)',
            r'\1presence-icon.png\2',
            document,
            count=1,
        )
        if updated != document:
            write_document(path, updated)

    source_bytes = sum((ROOT / source).stat().st_size for source in converted)
    target_bytes = sum((ROOT / target).stat().st_size for target in set(converted.values()))
    reduction = (1 - target_bytes / source_bytes) * 100 if source_bytes else 0
    print(
        f"Converted {len(converted)} referenced images: "
        f"{source_bytes / 1024 / 1024:.1f} MB -> {target_bytes / 1024 / 1024:.1f} MB "
        f"({reduction:.1f}% smaller)"
    )


if __name__ == "__main__":
    main()
