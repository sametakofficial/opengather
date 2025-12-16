"""
Media Filename Parser

Parses movie and TV show filenames to extract:
- Title (with dual-language support)
- Year
- Season/Episode numbers
- Absolute episode numbers

Supports multiple naming conventions:
- Standard: Show.S01E02.mkv
- Scene: Show.1x02.mkv
- Absolute: Show.Episode.15.mkv
- Turkish: Dizi.1.Sezon.5.Bolum.mkv
"""

import re
from typing import Tuple, Optional, List

# Quality indicators to remove from filenames
QUALITY_KEYWORDS: List[str] = [
    "4K", "2160p", "1080p", "720p", "480p", "UHD",
    "BluRay", "BDRip", "BRRip", "WEB-DL", "WEBDL",
    "WEBRip", "HDTV", "DVDRip", "PROPER", "EXTENDED", "BR",
    "TSRG", "YIFY", "RARBG", "FGT", "SPARKS", "ROVERS",
    "DSNP", "NF", "AMZN", "ATVP", "HMAX", "PMTP", "DSNP",
    "TURG", "BYNDR", "Xvid", "TR"
]

# Codec indicators to remove from filenames
CODEC_KEYWORDS: List[str] = [
    "x264", "x265", "H.264", "H.265", "H 264", "H 265", "HEVC",
    "10bit", "10Bit", "DTS-HD", "DTS", "Atmos", "TrueHD",
    "AC3", "DD+5.1", "DDP5.1", "DDP5 1", "AAC", "Dolby 5.1", "Dolby 5 1"
]

# Language indicators to remove from filenames
LANGUAGE_KEYWORDS: List[str] = [
    "FR EN", "MULTI", "TRUEFRENCH", "FRENCH",
    "DUAL", "TR-EN", "TR Dublaj", "Dublaj"
]
# Combined keywords for removal
ALL_DEFAULT_KEYWORDS: List[str] = QUALITY_KEYWORDS + CODEC_KEYWORDS + LANGUAGE_KEYWORDS
_JOINED_DEFAULT = "|".join([re.escape(k) for k in ALL_DEFAULT_KEYWORDS if k])

# Compiled regex patterns for performance
DEFAULT_DELETE_REGEX = re.compile(rf"(?i)[\s\._]?({_JOINED_DEFAULT})\b|[\(\[].*?[\)\]]|\s+$")
SPACE_REGEX = re.compile(r"[._]")
EXTRACT_DATE_REGEX = re.compile(r"^(.+?)[\s\._-]*\(?(19\d{2}|20\d{2})\)?.*$")

# Episode keywords in multiple languages
EPISODE_KEYWORDS: List[str] = [
    "episode", "episodio", "bolum",  # Common
    "Folge",  # German
]
_JOINED_EPISODE_KEYWORDS = "|".join([re.escape(k) for k in EPISODE_KEYWORDS])

# Classic patterns - highest reliability, tried first
CLASSIC_PATTERNS: List[re.Pattern] = [
    re.compile(rf"(?i)^(?P<name>.+?)[\.\s]S(?P<season>\d{{1,2}})E(?P<episode>\d{{1,3}})"),
    re.compile(rf"(?i)^(?P<name>.+?)[\.\s](?P<season>\d{{1,2}})x(?P<episode>\d{{1,3}})"),
    re.compile(rf"(?i)^(?P<name>.+?)[\.\s](?P<kw>{_JOINED_EPISODE_KEYWORDS})[\.\s]?(?P<episode>\d{{1,3}})")
]

# Loose season patterns - fallback for non-standard naming
SEASON_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)\bS(?:eason)?\s*(?P<season>\d{1,2})\b"),
    re.compile(r"(?i)\bSezon\s*(?P<season>\d{1,2})\b"),
    re.compile(r"(?i)\b(?P<season>\d{1,2})\s*\.?\s*S\b"),
]
# Loose episode patterns - fallback for non-standard naming
EPISODE_PATTERNS_LOOSE: List[re.Pattern] = [
    re.compile(r"(?i)\bE(?:pisode)?\s*(?P<episode>\d{1,3})\b"),
    re.compile(r"(?i)\bEp\.?\s*(?P<episode>\d{1,3})\b"),
    re.compile(r"(?i)\bB[öo]l[üu]m\s*(?P<episode>\d{1,3})\b"),  # Turkish
]

# Absolute episode patterns (no season)
ABS_EP_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)\b(?P<abs>\d{1,3})\s*\.?\s*B[öo]l[üu]m\b"),  # Turkish
    re.compile(r"(?i)\bB[öo]l[üu]m\s*(?P<abs>\d{1,3})\b"),  # Turkish
    re.compile(r"(?i)\bEp\.?\s*(?P<abs>\d{1,3})\b"),
]

# Combined season+episode patterns
COMBINED_SEASON_EPISODE: List[re.Pattern] = [
    re.compile(r"(?i)\bS(?P<season>\d{1,2})\s*E(?P<episode>\d{1,3})\b"),
    re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"),
    re.compile(r"(?i)\bS\s*(?P<season>\d{1,2}).{0,6}E[p]?\s*(?P<episode>\d{1,3})"),
    re.compile(r"(?i)\[(?P<season>\d{1,2})\s*\.?\s*S(?:[^0-9]+|\.|\s)*E[p]?\s*(?P<episode>\d{1,3})\]"),
]

# Year extraction pattern
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def _strip_leading_brackets(s: str) -> str:
    """Remove leading bracketed content from string."""
    return re.sub(r"^\s*(\[[^\]]*\]\s*)+", '', s)


def sanitize_string(s: str, custom_delete_keywords: Optional[List[str]] = None) -> str:
    """
    Clean filename string by removing quality/codec keywords and normalizing.
    
    Args:
        s: Input filename string
        custom_delete_keywords: Additional keywords to remove
        
    Returns:
        Cleaned string with keywords removed and spaces normalized
    """
    # Replace dots/underscores with spaces
    s = SPACE_REGEX.sub(' ', s)
    
    # Remove quality/codec keywords
    for kw in ALL_DEFAULT_KEYWORDS:
        if kw:
            s = re.sub(rf"(?i)\b{re.escape(kw)}\b", ' ', s)
    
    # Remove brackets and their contents
    s = re.sub(r'[\(\[].*?[\)\]]', ' ', s)
    
    # Custom keywords
    if custom_delete_keywords:
        for kw in custom_delete_keywords:
            if kw:
                s = re.sub(rf"(?i)\b{re.escape(kw)}\b", ' ', s)
    
    # Clean up multiple spaces
    s = re.sub(r"\s+", ' ', s).strip()
    return s

def _guess_show_name(cleaned: str) -> str:
    """Extract show name from cleaned string, stopping at season/episode markers."""
    s = _strip_leading_brackets(cleaned)
    if ' - ' in s:
        left = s.split(' - ', 1)[0].strip()
        if left: return left
    m = re.search(r"(?i)\b(S(?:eason)?\s*\d+|Sezon\s*\d+|\d+\s*\.?\s*S|E(?:p|pisode)?\s*\d+|B[öo]l[üu]m\s*\d+)\b", s)
    if m:
        left = s[:m.start()].strip()
        if left: return left
    return s.strip()

def _classic_try(s: str) -> Optional[Tuple[str, int, int]]:
    """Try classic S01E02 or 1x02 patterns. Returns (name, season, episode) or None."""
    for patt in CLASSIC_PATTERNS:
        m = patt.search(s)
        if m:
            gd = m.groupdict()
            name = gd.get("name", "").strip() or s[:m.start()].strip()
            season = int(gd.get("season") or 1)
            episode = int(gd.get("episode") or 1)
            return name, season, episode
    return None

def _wide_try(s: str) -> Tuple[Optional[int], Optional[int]]:
    """Try loose patterns for season/episode. Returns (season, episode) tuple."""
    for patt in COMBINED_SEASON_EPISODE:
        m = patt.search(s)
        if m:
            return int(m['season']), int(m['episode'])
    # Try separate patterns
    season = episode = None
    for p in SEASON_PATTERNS:
        m = p.search(s)
        if m:
            try:
                season = int(m['season'])
                break
            except (ValueError, KeyError, TypeError):
                pass
    for p in EPISODE_PATTERNS_LOOSE:
        m = p.search(s)
        if m:
            try:
                episode = int(m['episode'])
                break
            except (ValueError, KeyError, TypeError):
                pass
    return season, episode

def _abs_try(s: str) -> Optional[int]:
    """Try to extract absolute episode number (no season)."""
    for p in ABS_EP_PATTERNS:
        m = p.search(s)
        if m:
            try:
                return int(m.group('abs'))
            except (ValueError, AttributeError, KeyError):
                pass
    return None

def parse_movie_name(
    name_without_ext: str, 
    custom_delete_keywords: Optional[List[str]] = None
) -> Tuple[str, Optional[int]]:
    """
    Parse movie filename to extract title and year.
    
    Args:
        name_without_ext: Filename without extension
        custom_delete_keywords: Additional keywords to remove
        
    Returns:
        Tuple of (title, year) where year may be None
        
    Examples:
        >>> parse_movie_name("Mr. & Mrs. Smith (2005) BluRay 1080p")
        ('Mr & Mrs Smith', 2005)
    """
    # First extract year BEFORE sanitizing (to catch (2005) format)
    year_match = re.search(r'\(?(19\d{2}|20\d{2})\)?', name_without_ext)
    year = int(year_match.group(1)) if year_match else None
    
    # Remove year from string before sanitizing
    if year_match:
        name_without_year = name_without_ext[:year_match.start()] + name_without_ext[year_match.end():]
    else:
        name_without_year = name_without_ext
    
    # Now sanitize
    cleaned = sanitize_string(name_without_year, custom_delete_keywords)
    
    if ' - ' in cleaned:
        parts = cleaned.split(' - ')
        cleaned = parts[-1].strip()
    
    cleaned = cleaned.strip(' -')
    
    return cleaned.title(), year

def parse_show_name(
    name_without_ext: str, 
    custom_delete_keywords: Optional[List[str]] = None, 
    exclude_unparsed: bool = False
) -> Tuple[str, int, int, bool]:
    """
    Parse TV show filename to extract show name, season, and episode.
    
    Args:
        name_without_ext: Filename without extension
        custom_delete_keywords: Additional keywords to remove
        exclude_unparsed: Return empty result if parsing fails
        
    Returns:
        Tuple of (show_name, season, episode, is_unparsed)
        - season=0 indicates absolute episode numbering
        - is_unparsed=True if parsing failed and exclude_unparsed=True
        
    Examples:
        >>> parse_show_name("Breaking.Bad.S01E02.720p")
        ('Breaking Bad', 1, 2, False)
        >>> parse_show_name("Anime.Episode.15")
        ('Anime', 0, 15, False)  # Absolute episode
    """
    # Step 0: Minimal normalization (dots/underscores to spaces), preserve brackets
    pre = SPACE_REGEX.sub(' ', name_without_ext)

    # Step 1: Try classic patterns first (most reliable)
    c = _classic_try(pre)
    if c:
        name, season, episode = c
        show = sanitize_string(name, custom_delete_keywords).title()
        return show, season, episode, False

    # Step 2: Try loose patterns
    season, episode = _wide_try(pre)
    
    # Check if there's a season marker
    has_season_marker = season is not None or bool(
        re.search(r"(?i)\bS(?:eason)?\s*\d+\b|\bSezon\s*\d+\b|\b\d+\s*\.?\s*S\b|\b\d+x\d+\b", pre)
    )
    
    # Try absolute episode number
    abs_ep = _abs_try(pre)

    if (not has_season_marker) and (abs_ep is not None):
        season, episode = 0, abs_ep

    # Guess show name
    show_name = sanitize_string(_guess_show_name(pre), custom_delete_keywords).title()

    # Default to season 1, episode 1 if not found
    if season is None:
        season = 1
    if episode is None:
        episode = 1

    if exclude_unparsed and (not show_name or len(show_name) < 2):
        return '', 0, 0, True
    return show_name, int(season), int(episode), False
