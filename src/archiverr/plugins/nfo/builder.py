"""Build Kodi-compatible NFO XML from a flat show/movie entity.

The entity shape follows PLUGIN_CONVENTIONS (TMDb reference). Missing
fields stay omitted. No plugin names live here.
"""

from __future__ import annotations

from xml.sax.saxutils import escape
from typing import Any


def title_of(entity: dict[str, Any]) -> str:
    title = entity.get("title")
    if isinstance(title, dict):
        return str(title.get("primary") or title.get("original") or "")
    if isinstance(title, str):
        return title
    return str(entity.get("name") or "")


def original_title_of(entity: dict[str, Any]) -> str:
    title = entity.get("title")
    if isinstance(title, dict):
        return str(title.get("original") or title.get("primary") or "")
    return title_of(entity)


def year_of(entity: dict[str, Any]) -> int | None:
    year = entity.get("year")
    if year is None:
        year = (entity.get("release") or {}).get("year") if isinstance(entity.get("release"), dict) else None
    if year is None:
        year = (entity.get("air_dates") or {}).get("year") if isinstance(entity.get("air_dates"), dict) else None
    try:
        return int(year) if year is not None else None
    except (TypeError, ValueError):
        return None


def ids_of(entity: dict[str, Any]) -> dict[str, str]:
    raw = entity.get("identifiers") or {}
    if not isinstance(raw, dict):
        raw = {}
    out: dict[str, str] = {}
    for key in ("imdb_id", "tmdb_id", "tvdb_id", "tvmaze_id"):
        val = raw.get(key) or entity.get(key)
        if val:
            out[key] = str(val)
    return out


def genres_of(entity: dict[str, Any]) -> list[str]:
    genres = entity.get("genres")
    if isinstance(genres, str):
        return [genres] if genres else []
    if isinstance(genres, list):
        names = []
        for item in genres:
            if isinstance(item, str) and item:
                names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        return names
    return []


def _tag(name: str, value: Any, **attrs: str) -> str:
    if value is None or value == "":
        return ""
    attr = "".join(f' {k}="{escape(str(v))}"' for k, v in attrs.items() if v)
    return f"  <{name}{attr}>{escape(str(value))}</{name}>\n"


def _genres_xml(entity: dict[str, Any]) -> str:
    return "".join(_tag("genre", g) for g in genres_of(entity))


def build_movie_nfo(entity: dict[str, Any]) -> str:
    ids = ids_of(entity)
    runtime = entity.get("runtime")
    plot = entity.get("overview") or entity.get("plot") or ""
    body = (
        _tag("title", title_of(entity))
        + _tag("originaltitle", original_title_of(entity))
        + _tag("year", year_of(entity))
        + _tag("plot", plot)
        + _tag("runtime", runtime)
        + _tag("id", ids.get("imdb_id"))
        + _tag("uniqueid", ids.get("imdb_id"), type="imdb")
        + _tag("uniqueid", ids.get("tmdb_id"), type="tmdb")
        + _tag("tmdbid", ids.get("tmdb_id"))
        + _genres_xml(entity)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<movie>\n{body}</movie>\n"
    )


def build_episode_nfo(entity: dict[str, Any]) -> str:
    ids = ids_of(entity)
    plot = entity.get("episode_overview") or entity.get("overview") or ""
    ep_title = entity.get("episode_title") or title_of(entity)
    body = (
        _tag("title", ep_title)
        + _tag("showtitle", title_of(entity))
        + _tag("season", entity.get("season_number"))
        + _tag("episode", entity.get("episode_number"))
        + _tag("aired", entity.get("episode_air_date"))
        + _tag("plot", plot)
        + _tag("runtime", entity.get("episode_runtime") or entity.get("runtime"))
        + _tag("uniqueid", ids.get("imdb_id"), type="imdb")
        + _tag("uniqueid", ids.get("tmdb_id"), type="tmdb")
        + _tag("tmdbid", ids.get("tmdb_id"))
        + _genres_xml(entity)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<episodedetails>\n{body}</episodedetails>\n"
    )


def build_nfo(category: str, entity: dict[str, Any]) -> str:
    if category == "show":
        return build_episode_nfo(entity)
    return build_movie_nfo(entity)


def pick_entity(
    plugins: dict[str, Any],
    envelope: Any = None,
    job_index: int | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Choose (category, entity) without naming data providers.

    Order: run.data envelope for this job index, then any plugin payload
    that already has a show/movie dict, then renamer.parsed as last resort.
    """
    from_env = _from_envelope(envelope, job_index)
    if from_env:
        return from_env

    if not isinstance(plugins, dict):
        return None

    for payload in plugins.values():
        picked = _from_payload(payload)
        if picked:
            return picked

    return _from_renamer(plugins.get("renamer") or {})


def _from_envelope(envelope: Any, job_index: int | None) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(envelope, dict) or job_index is None:
        return None
    block = envelope.get(job_index)
    if block is None:
        block = envelope.get(str(job_index))
    if not isinstance(block, dict):
        return None
    if isinstance(block.get("movie"), dict) and block["movie"]:
        return "movie", block["movie"]
    if isinstance(block.get("show"), dict) and block["show"]:
        return "show", block["show"]
    return None


def _from_payload(payload: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(payload, dict):
        return None
    movie = payload.get("movie")
    show = payload.get("show")
    if isinstance(movie, dict) and (title_of(movie) or movie.get("name")):
        return "movie", movie
    if isinstance(show, dict) and (title_of(show) or show.get("name")):
        return "show", show
    return None


def _from_renamer(renamer: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    parsed = renamer.get("parsed") or {}
    category = renamer.get("category")
    movie = parsed.get("movie") if isinstance(parsed, dict) else None
    show = parsed.get("show") if isinstance(parsed, dict) else None
    if category == "movie" and isinstance(movie, dict) and movie.get("name"):
        return "movie", {
            "title": {"primary": movie.get("name")},
            "release": {"year": movie.get("year")},
        }
    if category == "show" and isinstance(show, dict) and show.get("name"):
        return "show", {
            "title": {"primary": show.get("name")},
            "season_number": show.get("season"),
            "episode_number": show.get("episode"),
            "episode_title": show.get("title") or show.get("episode_title"),
        }
    if isinstance(movie, dict) and movie.get("name"):
        return _from_renamer({**renamer, "category": "movie"})
    if isinstance(show, dict) and show.get("name"):
        return _from_renamer({**renamer, "category": "show"})
    return None
