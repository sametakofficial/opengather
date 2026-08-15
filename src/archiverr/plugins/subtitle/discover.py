"""Find subtitle sidecars next to a media file.

Does not download. Does not parse containers. Filename convention only:

    Movie.2010.mkv
    Movie.2010.srt
    Movie.2010.en.srt
    Movie.2010.tr.forced.srt
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_EXTENSIONS = ("srt", "ass", "ssa", "sub", "vtt")


def normalize_extensions(raw: Any) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_EXTENSIONS
    out: list[str] = []
    for item in raw:
        ext = str(item).lstrip(".").lower()
        if ext and ext not in out:
            out.append(ext)
    return tuple(out) or DEFAULT_EXTENSIONS


def language_of(stem: str, media_stem: str) -> str:
    """``Movie.2010.en.forced`` → ``en`` when media stem is ``Movie.2010``."""
    if not stem.lower().startswith(media_stem.lower()):
        return ""
    rest = stem[len(media_stem):].lstrip(".")
    if not rest:
        return ""
    token = rest.split(".")[0].lower()
    if token in {"forced", "sdh", "hi", "cc"}:
        return ""
    return token


def discover_sidecars(media_path: str | Path, extensions: Any = None) -> list[dict[str, Any]]:
    path = Path(media_path)
    if not path.parent.exists():
        return []

    media_stem = path.stem
    prefix = media_stem.lower()
    exts = set(normalize_extensions(extensions))
    found: list[dict[str, Any]] = []

    for candidate in sorted(path.parent.iterdir()):
        if not candidate.is_file():
            continue
        if candidate.suffix.lstrip(".").lower() not in exts:
            continue
        if not candidate.stem.lower().startswith(prefix):
            continue
        if candidate.resolve() == path.resolve():
            continue
        found.append({
            "path": str(candidate),
            "filename": candidate.name,
            "extension": candidate.suffix.lstrip(".").lower(),
            "language": language_of(candidate.stem, media_stem),
            "size_bytes": candidate.stat().st_size,
        })
    return found
