# PLUGINS - COMPLETE IMPLEMENTATION REFERENCE

## PLUGIN STRUCTURE (ALL 8 PLUGINS)

```
plugins/
├── scanner/          INPUT  - File/directory scanning
├── file-reader/      INPUT  - Read paths from targets.txt
├── ffprobe/          OUTPUT - Video analysis (ffprobe wrapper)
├── renamer/          OUTPUT - Filename parsing (movie/show detection)
├── tmdb/             OUTPUT - TMDb API metadata
├── tvdb/             OUTPUT - TVDb API metadata
├── tvmaze/           OUTPUT - TVMaze API metadata
├── omdb/             OUTPUT - OMDb API metadata (IMDb ratings)
└── mock_test/        TEST   - Testing plugin
```

---

## INPUT PLUGINS

### 1. SCANNER PLUGIN

**Files:**
- `plugins/scanner/plugin.json`
- `plugins/scanner/client.py`

**plugin.json:**
```json
{
  "name": "scanner",
  "version": "1.0.0",
  "category": "input",
  "categories": [],
  "depends_on": [],
  "expects": []
}
```

**Class:** `ScannerPlugin`

**Config:**
```yaml
plugins:
  scanner:
    enabled: true
    targets:
      - /path/to/media
      - /path/to/file.mkv
    recursive: false  # true = scan subdirectories
    allow_virtual_paths: false  # true = allow non-existent paths
```

**Constructor:**
```python
def __init__(self, config: Dict[str, Any]):
    self.config = config
    self.name = "scanner"
    self.category = "input"
    self.debugger = get_debugger()
```

**Method:** `execute(match_data=None) -> List[Dict]`

**Logic:**
```python
def execute(self, match_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    targets = self.config.get('targets', [])
    recursive = self.config.get('recursive', True)
    allow_virtual = self.config.get('allow_virtual_paths', False)
    
    results = []
    
    for target in targets:
        # Skip .txt files (for file_reader)
        if target.endswith('.txt'):
            continue
        
        target_path = Path(target)
        
        # Case 1: Direct file
        if target_path.is_file():
            results.append({
                'status': {
                    'success': True,
                    'started_at': start_time.isoformat(),
                    'finished_at': end_time.isoformat(),
                    'duration_ms': duration_ms
                },
                'input': {
                    'path': str(target_path),
                    'virtual': False
                }
            })
        
        # Case 2: Directory (recursive scanning)
        elif target_path.is_dir() and recursive:
            for ext in ['.mkv', '.mp4', '.avi', '.m4v', '.ts']:
                for file in target_path.rglob(f'*{ext}'):
                    if file.is_file():
                        results.append({...})
        
        # Case 3: Virtual path (non-existent, for testing)
        elif allow_virtual and not target_path.exists():
            results.append({
                'input': {
                    'path': target,
                    'virtual': True
                }
            })
    
    return results
```

**Output Format:**
```python
[
    {
        'status': {...},
        'input': {
            'path': '/path/file.mkv',
            'virtual': False
        }
    },
    ...
]
```

**Supported Extensions:**
- `.mkv`
- `.mp4`
- `.avi`
- `.m4v`
- `.ts`

---

### 2. FILE-READER PLUGIN

**Files:**
- `plugins/file-reader/plugin.json`
- `plugins/file-reader/client.py`

**plugin.json:**
```json
{
  "name": "file-reader",
  "version": "1.0.0",
  "category": "input",
  "class_name": "FileReaderPlugin",
  "categories": [],
  "depends_on": [],
  "expects": []
}
```

**Class:** `FileReaderPlugin`

**Config:**
```yaml
plugins:
  file-reader:
    enabled: true
    targets:
      - tests/targets.txt
    allow_virtual_paths: true
```

**Method:** `execute(match_data=None) -> List[Dict]`

**Logic:**
```python
def execute(self, match_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    targets = self.config.get('targets', [])
    allow_virtual = self.config.get('allow_virtual_paths', False)
    
    results = []
    
    for target_file in targets:
        if not target_file.endswith('.txt'):
            continue
        
        target_path = Path(target_file)
        
        if not target_path.exists():
            self.debugger.warn("file_reader", f"File not found: {target_file}")
            continue
        
        # Read lines from file
        with open(target_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            path = line.strip()
            
            if not path or path.startswith('#'):
                continue
            
            file_path = Path(path)
            is_virtual = not file_path.exists()
            
            if is_virtual and not allow_virtual:
                continue
            
            results.append({
                'status': {...},
                'input': {
                    'path': path,
                    'virtual': is_virtual
                }
            })
    
    return results
```

**targets.txt Format:**
```
# Comment line (ignored)
/path/to/file1.mkv
/path/to/file2.mp4
/virtual/path/file3.mkv  # Allowed if allow_virtual_paths=true
```

---

## OUTPUT PLUGINS

### 3. FFPROBE PLUGIN

**Files:**
- `plugins/ffprobe/plugin.json`
- `plugins/ffprobe/client.py`
- `plugins/ffprobe/ffprobe_wrapper.py`

**plugin.json:**
```json
{
  "name": "ffprobe",
  "version": "1.0.0",
  "category": "output",
  "class_name": "FFProbePlugin",
  "categories": [],
  "depends_on": [],
  "expects": ["input"]
}
```

**Class:** `FFProbePlugin`

**Config:**
```yaml
plugins:
  ffprobe:
    enabled: true
    timeout: 15  # seconds
```

**Method:** `execute(match_data) -> Dict`

**Dependencies:**
- External: `ffprobe` binary (from ffmpeg package)

**Logic:**
```python
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    input_metadata = match_data.get('input', {})
    input_path = input_metadata.get('path')
    is_virtual = input_metadata.get('virtual', False)
    
    if not input_path or is_virtual:
        return error_result
    
    if not Path(input_path).exists():
        return error_result
    
    # Run ffprobe
    wrapper = FFProbe(input_path, self.timeout)
    success, error = wrapper.probe()
    
    if not success:
        return error_result
    
    # Extract data
    video_stream = wrapper.get_video_stream()
    audio_streams = wrapper.get_audio_streams()
    subtitle_streams = wrapper.get_subtitle_streams()
    container_info = wrapper.get_container()
    
    return {
        'status': {...},
        'video': {
            'codec_name': video_stream.get('codec_name'),
            'codec_long_name': video_stream.get('codec_long_name'),
            'profile': video_stream.get('profile'),
            'width': int(video_stream.get('width', 0)),
            'height': int(video_stream.get('height', 0)),
            'fps': self._calculate_fps(video_stream.get('r_frame_rate', '0/1')),
            'bit_rate': int(video_stream.get('bit_rate', 0)),
            'duration_seconds': float(video_stream.get('duration', 0))
        },
        'audio': [
            {
                'index': stream.get('index'),
                'codec_name': stream.get('codec_name'),
                'codec_long_name': stream.get('codec_long_name'),
                'channels': int(stream.get('channels', 0)),
                'sample_rate': int(stream.get('sample_rate', 0)),
                'language': stream.get('tags', {}).get('language', 'und')
            }
            for stream in audio_streams
        ],
        'subtitles': [
            {
                'index': stream.get('index'),
                'codec_name': stream.get('codec_name'),
                'language': stream.get('tags', {}).get('language', 'und'),
                'forced': stream.get('disposition', {}).get('forced', 0) == 1
            }
            for stream in subtitle_streams
        ],
        'container': {
            'format_name': container_info.get('format_name'),
            'format_long_name': container_info.get('format_long_name'),
            'duration': float(container_info.get('duration', 0)),
            'size_bytes': int(container_info.get('size', 0)),
            'bit_rate': int(container_info.get('bit_rate', 0))
        }
    }
```

**FFProbe Wrapper:**
```python
class FFProbe:
    def __init__(self, file_path: str, timeout: int = 15):
        self.file_path = file_path
        self.timeout = timeout
        self.data = None
    
    def probe(self) -> Tuple[bool, Optional[str]]:
        """Run ffprobe and parse JSON output"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            self.file_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
                text=True
            )
            
            if result.returncode != 0:
                return (False, result.stderr)
            
            self.data = json.loads(result.stdout)
            return (True, None)
        
        except subprocess.TimeoutExpired:
            return (False, f"Timeout after {self.timeout}s")
        except Exception as e:
            return (False, str(e))
    
    def get_video_stream(self) -> Optional[Dict]:
        """Get first video stream"""
        if not self.data:
            return None
        
        for stream in self.data.get('streams', []):
            if stream.get('codec_type') == 'video':
                return stream
        
        return None
```

**Output Structure:**
```python
{
    'status': {...},
    'video': {
        'codec_name': 'hevc',
        'width': 1920,
        'height': 816,
        'fps': 23.976,
        'duration_seconds': 7200.0
    },
    'audio': [
        {
            'codec_name': 'ac3',
            'channels': 6,
            'language': 'eng'
        }
    ],
    'subtitles': [...],
    'container': {
        'format_name': 'matroska,webm',
        'duration': 7200.0,
        'size_bytes': 12345678
    }
}
```

---

### 4. RENAMER PLUGIN

**Files:**
- `plugins/renamer/plugin.json`
- `plugins/renamer/client.py`
- `plugins/renamer/parser.py`

**plugin.json:**
```json
{
  "name": "renamer",
  "version": "1.0.0",
  "category": "output",
  "categories": ["movie", "show"],
  "depends_on": [],
  "expects": ["input"]
}
```

**Class:** `RenamerPlugin`

**Config:**
```yaml
plugins:
  renamer:
    enabled: true
    media_type: auto  # auto, movie, show
```

**Method:** `execute(match_data) -> Dict`

**Logic:**
```python
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    input_metadata = match_data.get('input', {})
    input_path = input_metadata.get('path')
    
    filename = Path(input_path).stem
    
    # Parse based on media_type
    show_match = None
    movie_match = None
    
    if self.media_type == 'auto':
        # Try movie first (year is strong indicator)
        movie_match = self._parse_movie(filename)
        
        # Only try show if NO movie with year found
        if not (movie_match and movie_match.get('year')):
            show_match = self._parse_show(filename)
            movie_match = None
    
    elif self.media_type == 'show':
        show_match = self._parse_show(filename)
    
    elif self.media_type == 'movie':
        movie_match = self._parse_movie(filename)
    
    # Determine category
    category = 'unknown'
    if movie_match and movie_match.get('name'):
        category = 'movie'
    elif show_match and show_match.get('name'):
        category = 'show'
    
    return {
        'status': {...},
        'parsed': {
            'show': show_match,
            'movie': movie_match
        },
        'category': category
    }
```

**Parser Functions (`parser.py`):**

#### `parse_movie_name(filename: str) -> Tuple[str, Optional[int]]`
```python
def parse_movie_name(filename: str) -> Tuple[str, Optional[int]]:
    """
    Parse movie filename
    
    Examples:
        "Mr. & Mrs. Smith (2005)" -> ("Mr. & Mrs. Smith", 2005)
        "Movie.Name.2024.1080p" -> ("Movie Name", 2024)
        "Türkçe - English (2024)" -> ("Türkçe - English", 2024)
    
    Returns:
        (movie_name, year)
    """
    # Pattern: Name (Year) or Name.Year
    year_pattern = r'\((\d{4})\)|\.(\d{4})\.'
    
    match = re.search(year_pattern, filename)
    
    if match:
        year = int(match.group(1) or match.group(2))
        # Extract name before year
        name_part = filename[:match.start()]
    else:
        year = None
        name_part = filename
    
    # Clean name
    name = sanitize_string(name_part)
    
    return (name, year)


def sanitize_string(s: str) -> str:
    """
    Clean filename string
    
    Examples:
        "Movie.Name" -> "Movie Name"
        "Movie_Name" -> "Movie Name"
        "Movie  Name" -> "Movie Name"
    """
    # Replace dots/underscores with spaces
    s = s.replace('.', ' ').replace('_', ' ')
    
    # Remove quality markers
    quality_patterns = ['1080p', '720p', '480p', '4k', 'bluray', 'webrip', 'hdtv']
    for pattern in quality_patterns:
        s = re.sub(pattern, '', s, flags=re.IGNORECASE)
    
    # Remove multiple spaces
    s = re.sub(r'\s+', ' ', s)
    
    return s.strip()
```

#### `parse_show_name(filename: str) -> Tuple[str, int, int, bool]`
```python
def parse_show_name(filename: str) -> Tuple[str, int, int, bool]:
    """
    Parse TV show filename
    
    Examples:
        "Show.Name.S01E05" -> ("Show Name", 1, 5, False)
        "Show.Name.1x05" -> ("Show Name", 1, 5, False)
        "Show Name - S01E05" -> ("Show Name", 1, 5, False)
    
    Returns:
        (show_name, season, episode, failed)
    """
    # Pattern: S01E05 or 1x05
    patterns = [
        r'[Ss](\d{1,2})[Ee](\d{1,2})',  # S01E05
        r'(\d{1,2})x(\d{1,2})'          # 1x05
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            
            # Extract name before pattern
            name_part = filename[:match.start()]
            name = sanitize_string(name_part)
            
            return (name, season, episode, False)
    
    # No match found
    return ('', 0, 0, True)
```

**Output Structure:**
```python
{
    'status': {...},
    'parsed': {
        'show': {
            'name': 'Breaking Bad',
            'season': 1,
            'episode': 1
        },
        'movie': {
            'name': 'Mr. & Mrs. Smith',
            'year': 2005
        }
    },
    'category': 'movie'  # or 'show' or 'unknown'
}
```

---

### 5. TMDB PLUGIN

**Files:**
- `plugins/tmdb/plugin.json`
- `plugins/tmdb/client.py`
- `plugins/tmdb/api/tmdb_api.py`
- `plugins/tmdb/extras.py`
- `plugins/tmdb/normalize/normalizer.py`
- `plugins/tmdb/utils/fetchers.py`

**plugin.json:**
```json
{
  "name": "tmdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TMDbPlugin",
  "categories": ["movie", "show"],
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"]
}
```

**Class:** `TMDbPlugin(OutputPlugin)`

**Config:**
```yaml
plugins:
  tmdb:
    enabled: true
    api_key: "${TMDB_API_KEY}"
    language: tr-TR
    region: TR
    include-raw: true
    extras:
      movie_credits: true
      movie_images: true
      movie_keywords: true
      movie_videos: true
      tv_credits: true
      tv_episode_credits: true
      tv_images: true
      tv_keywords: true
```

**Architecture:**
```
TMDbPlugin (client.py)
├── TMDbAPI (utils/api.py)          - Low-level HTTP requests
├── TMDbExtras (extras.py)          - Extra API endpoints
├── TMDbNormalizer (normalize/)     - Response normalization
└── Fetchers (utils/fetchers.py)
    ├── TMDbMovieFetcher
    └── TMDbShowFetcher
```

**Constructor:**
```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)
    self.api_key = config.get('api_key', '')
    self.lang = config.get('language', 'en-US')
    self.region = config.get('region', 'TR')
    self.include_raw = config.get('include-raw', False)
    
    # Components
    self.api = TMDbAPI(self.api_key, self.lang, self.region)
    self.extras_client = TMDbExtras(self.api_key, self.lang)
    self.normalizer = TMDbNormalizer()
    
    # Extras config
    self.extras_config = config.get('extras', {})
    
    # Fetchers
    self.movie_fetcher = TMDbMovieFetcher(
        self.api, self.extras_client, self.normalizer,
        self.extras_config, self.include_raw, self.debugger
    )
    self.show_fetcher = TMDbShowFetcher(
        self.api, self.extras_client, self.normalizer,
        self.extras_config, self.include_raw, self.debugger
    )
```

**Method:** `execute(match_data) -> Dict`

**Logic:**
```python
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    renamer_data = match_data.get('renamer', {})
    parsed_data = renamer_data.get('parsed', {})
    
    movie_data = parsed_data.get('movie')
    show_data = parsed_data.get('show')
    
    result = None
    
    # Route to fetcher
    if movie_data and movie_data.get('name'):
        result = self.movie_fetcher.fetch(
            movie_data.get('name'),
            movie_data.get('year')
        )
    elif show_data and show_data.get('name'):
        result = self.show_fetcher.fetch(
            show_data.get('name'),
            show_data.get('season'),
            show_data.get('episode')
        )
    
    # Add validation
    if result and result.get('status', {}).get('success'):
        result['validation'] = self._perform_validation(match_data, result)
    
    return result
```

**TMDbAPI Class:**
```python
class TMDbAPI:
    BASE_URL = 'https://api.themoviedb.org/3'
    
    def __init__(self, api_key: str, language: str, region: str):
        self.api_key = api_key
        self.language = language
        self.region = region
    
    def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request"""
        url = f"{self.BASE_URL}{endpoint}"
        
        default_params = {
            'api_key': self.api_key,
            'language': self.language
        }
        
        if params:
            default_params.update(params)
        
        response = requests.get(url, params=default_params, timeout=10)
        response.raise_for_status()
        
        return response.json()
    
    def search_movie(self, query: str, year: int = None) -> Dict:
        """Search for movie"""
        params = {'query': query}
        if year:
            params['year'] = year
        
        return self._request('/search/movie', params)
    
    def get_movie(self, movie_id: int) -> Dict:
        """Get movie details"""
        return self._request(f'/movie/{movie_id}')
    
    def search_tv(self, query: str) -> Dict:
        """Search for TV show"""
        return self._request('/search/tv', {'query': query})
    
    def get_tv_show(self, tv_id: int) -> Dict:
        """Get TV show details"""
        return self._request(f'/tv/{tv_id}')
    
    def get_season(self, tv_id: int, season_number: int) -> Dict:
        """Get season details"""
        return self._request(f'/tv/{tv_id}/season/{season_number}')
    
    def get_episode(self, tv_id: int, season: int, episode: int) -> Dict:
        """Get episode details"""
        return self._request(f'/tv/{tv_id}/season/{season}/episode/{episode}')
```

**Movie Fetcher:**
```python
class TMDbMovieFetcher:
    def fetch(self, movie_name: str, year: int = None) -> Dict:
        """
        Fetch movie metadata + extras
        
        Returns:
            {
                'status': {...},
                'movie': {...},
                'extras': {
                    'credits': {...},
                    'images': {...},
                    'keywords': {...},
                    'videos': {...}
                },
                'normalized': {...},
                'raw': {...}  # if include-raw=true
            }
        """
        start_time = datetime.now()
        
        # Search
        search_result = self.api.search_movie(movie_name, year)
        
        if not search_result.get('results'):
            return error_result
        
        # Get first result
        movie = search_result['results'][0]
        movie_id = movie['id']
        
        # Get details
        details = self.api.get_movie(movie_id)
        
        # Fetch extras
        extras = {}
        if self.extras_config.get('movie_credits'):
            extras['credits'] = self.extras_client.get_movie_credits(movie_id)
        if self.extras_config.get('movie_images'):
            extras['images'] = self.extras_client.get_movie_images(movie_id)
        if self.extras_config.get('movie_keywords'):
            extras['keywords'] = self.extras_client.get_movie_keywords(movie_id)
        if self.extras_config.get('movie_videos'):
            extras['videos'] = self.extras_client.get_movie_videos(movie_id)
        
        # Normalize
        normalized = self.normalizer.normalize_movie(details, extras)
        
        # Build result
        result = {
            'status': {...},
            'movie': details,
            'episode': None,
            'season': None,
            'show': None,
            'extras': extras,
            'normalized': normalized
        }
        
        if self.include_raw:
            result['raw'] = {
                'search': search_result,
                'details': details
            }
        
        return result
```

**Output Structure:**
```python
{
    'status': {...},
    'movie': {
        'id': 12345,
        'title': 'Movie Name',
        'original_title': 'Original Title',
        'release_date': '2025-01-01',
        'runtime': 120,
        'vote_average': 7.5,
        'overview': '...',
        'genres': [{'id': 28, 'name': 'Action'}],
        'production_companies': [...]
    },
    'extras': {
        'credits': {
            'cast': [
                {
                    'id': 123,
                    'name': 'Actor Name',
                    'character': 'Character',
                    'order': 0
                },
                ...
            ],
            'crew': [...]
        },
        'images': {
            'backdrops': [...],
            'posters': [...]
        },
        'keywords': {
            'keywords': [
                {'id': 1, 'name': 'keyword'}
            ]
        },
        'videos': {
            'results': [...]
        }
    },
    'normalized': {...},
    'validation': {
        'tests_passed': 1,
        'tests_total': 1,
        'details': {
            'duration_match': {
                'duration_actual': 7200,
                'duration_expected': 7200,
                'difference_seconds': 0,
                'tolerance_seconds': 600,
                'passed': True
            }
        }
    }
}
```

---

### 6. TVDB PLUGIN

**Files:**
- `plugins/tvdb/plugin.json`
- `plugins/tvdb/client.py`
- `plugins/tvdb/api/tvdb_api.py`
- `plugins/tvdb/extras.py`

**plugin.json:**
```json
{
  "name": "tvdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TVDbPlugin",
  "categories": ["movie", "show"],
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"]
}
```

**API:** TVDb v4 REST API
**Authentication:** Bearer token (JWT)

**Config:**
```yaml
plugins:
  tvdb:
    enabled: true
    api_key: "${TVDB_API_KEY}"
    include-raw: true
    extras:
      series_extended: true
      seasons_extended: true
      episodes_extended: true
      series_artworks: true
      movies_extended: true
      tags_options: true
```

**Similar structure to TMDb:**
- Search → Get details → Fetch extras → Normalize → Validate

---

### 7. TVMAZE PLUGIN

**Files:**
- `plugins/tvmaze/plugin.json`
- `plugins/tvmaze/client.py`
- `plugins/tvmaze/api/tvmaze_api.py`

**plugin.json:**
```json
{
  "name": "tvmaze",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TVMazePlugin",
  "categories": ["show"],
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"]
}
```

**API:** TVMaze API (no API key required)

**Config:**
```yaml
plugins:
  tvmaze:
    enabled: true
    include-raw: true
    extras:
      shows_cast: true
      shows_crew: true
      shows_episodes: true
      shows_images: true
      shows_seasons: true
      episodes_single: true
      episodes_guestcast: true
      episodes_guestcrew: true
```

**Note:** TVMaze only supports TV shows (no movies)

---

### 8. OMDB PLUGIN

**Files:**
- `plugins/omdb/plugin.json`
- `plugins/omdb/client.py`
- `plugins/omdb/api/omdb_api.py`

**plugin.json:**
```json
{
  "name": "omdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "OMDbPlugin",
  "categories": ["movie", "show"],
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"]
}
```

**API:** OMDb API (IMDb data)

**Config:**
```yaml
plugins:
  omdb:
    enabled: true
    api_key: "${OMDB_API_KEY}"
    include-raw: true
```

**Method:** `execute(match_data) -> Dict`

**Logic:**
```python
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    renamer_data = match_data.get('renamer', {})
    parsed_data = renamer_data.get('parsed', {})
    category = renamer_data.get('category')
    
    # Route based on category
    if category == 'movie':
        movie_data = parsed_data.get('movie')
        return self._fetch_movie(movie_data.get('name'), movie_data.get('year'))
    
    elif category == 'show':
        show_data = parsed_data.get('show')
        return self._fetch_episode(
            show_data.get('name'),
            show_data.get('season'),
            show_data.get('episode')
        )
    
    else:
        return error_result


def _fetch_movie(self, title: str, year: int) -> Dict:
    """Fetch movie from OMDb"""
    api_result = self.api.get_by_title(title, year, 'movie')
    
    # Parse runtime "120 min" -> 120
    runtime_str = api_result.get('Runtime', '0 min')
    runtime = int(runtime_str.split()[0]) if runtime_str != 'N/A' else 0
    
    return {
        'status': {...},
        'movie': {
            'imdb_id': api_result.get('imdbID'),
            'title': api_result.get('Title'),
            'year': int(api_result.get('Year', 0)),
            'runtime': runtime,
            'imdb_rating': float(api_result.get('imdbRating', 0)),
            'imdb_votes': api_result.get('imdbVotes'),
            'metascore': api_result.get('Metascore'),
            'genre': api_result.get('Genre'),
            'plot': api_result.get('Plot')
        },
        'episode': None,
        'raw': api_result if self.include_raw else None
    }
```

**Output Structure:**
```python
{
    'status': {...},
    'movie': {
        'imdb_id': 'tt0356910',
        'title': 'Mr. & Mrs. Smith',
        'year': 2005,
        'runtime': 120,
        'imdb_rating': 6.5,
        'imdb_votes': '500,000',
        'metascore': '55',
        'genre': 'Action, Comedy, Crime',
        'plot': '...'
    },
    'episode': None,
    'validation': {
        'tests_passed': 1,
        'tests_total': 1,
        'details': {...}
    }
}
```

---

## PLUGIN BASE CLASSES

### BasePlugin (`plugins/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass
from archiverr.utils.debug import get_debugger

@dataclass
class ValidationResult:
    tests_passed: int
    tests_total: int
    details: Dict[str, Any]
    
    @property
    def passed(self) -> bool:
        return self.tests_passed == self.tests_total


class BasePlugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debugger = get_debugger()
    
    @abstractmethod
    def execute(self, match_data: Dict[str, Any]) -> Any:
        """Execute plugin logic"""
        pass


class InputPlugin(BasePlugin):
    """Input plugins return List[Dict]"""
    
    @abstractmethod
    def execute(self, match_data: Dict = None) -> List[Dict]:
        """
        Returns list of matches
        
        Returns:
            [
                {
                    'status': {...},
                    'input': {'path': '...', 'virtual': False}
                },
                ...
            ]
        """
        pass


class OutputPlugin(BasePlugin):
    """Output plugins return Dict"""
    
    @abstractmethod
    def execute(self, match_data: Dict) -> Dict:
        """
        Process match data
        
        Args:
            match_data: {'input': {...}, 'renamer': {...}, 'ffprobe': {...}}
        
        Returns:
            {
                'status': {...},
                'validation': {...},
                ... plugin-specific data ...
            }
        """
        pass
    
    def _validate_duration(
        self,
        actual_seconds: int,
        expected_minutes: int,
        tolerance_seconds: int = 600
    ) -> ValidationResult:
        """
        Validate duration match
        
        Args:
            actual_seconds: From ffprobe
            expected_minutes: From API (runtime in minutes)
            tolerance_seconds: Acceptable difference (default: 10 minutes)
        
        Returns:
            ValidationResult with pass/fail and details
        """
        if not expected_minutes:
            return ValidationResult(
                tests_passed=0,
                tests_total=0,
                details={'skipped': 'No expected duration'}
            )
        
        expected_seconds = expected_minutes * 60
        difference = abs(actual_seconds - expected_seconds)
        passed = difference <= tolerance_seconds
        
        return ValidationResult(
            tests_passed=1 if passed else 0,
            tests_total=1,
            details={
                'duration_actual': actual_seconds,
                'duration_expected': expected_seconds,
                'difference_seconds': difference,
                'tolerance_seconds': tolerance_seconds,
                'passed': passed
            }
        )
```

---

## PLUGIN EXECUTION PATTERNS

### Pattern 1: Input Plugin (No Dependencies)
```python
class ScannerPlugin:
    def execute(self, match_data=None):
        # Ignores match_data (not used by input plugins)
        # Returns list of initial matches
        return [
            {'status': {...}, 'input': {...}},
            ...
        ]
```

### Pattern 2: Output Plugin (Expects Input)
```python
class FFProbePlugin(OutputPlugin):
    def execute(self, match_data):
        # Reads input
        input_path = match_data.get('input', {}).get('path')
        
        # Process
        result = analyze_video(input_path)
        
        # Returns single dict
        return {
            'status': {...},
            'video': {...},
            'audio': [...],
            'container': {...}
        }
```

### Pattern 3: Output Plugin (Expects Renamer)
```python
class TMDbPlugin(OutputPlugin):
    def execute(self, match_data):
        # Reads renamer result
        parsed = match_data.get('renamer', {}).get('parsed', {})
        
        # Get movie or show data
        movie = parsed.get('movie')
        show = parsed.get('show')
        
        # API call
        if movie:
            result = fetch_movie_metadata(movie['name'], movie['year'])
        elif show:
            result = fetch_show_metadata(show['name'], show['season'], show['episode'])
        
        # Validate (optional)
        if ffprobe_data := match_data.get('ffprobe'):
            validation = self._validate_duration(
                ffprobe_data['container']['duration'],
                result['movie']['runtime']
            )
            result['validation'] = validation
        
        return result
```

### Pattern 4: Category Propagation (Generic)
```python
# ANY plugin can provide 'category' field
# Core executor propagates it to input metadata

result = renamer_plugin.execute(match_data)
# result = {'category': 'movie', ...}

# Core executor checks:
if 'category' in result and 'input' in match_data:
    match_data['input']['category'] = result['category']
```

---

## PLUGIN COMMUNICATION

### Data Flow Example:

```
Input Phase:
  scanner.execute() -> [{'input': {'path': '/file.mkv', 'virtual': False}}]

Match 0 Processing:
  match_data = {'input': {'path': '/file.mkv', 'virtual': False}}
  
  Group 0 (parallel):
    ffprobe.execute(match_data)
      -> match_data['ffprobe'] = {video: {...}, audio: [...]}
    
    renamer.execute(match_data)
      -> match_data['renamer'] = {parsed: {movie: {...}}, category: 'movie'}
      -> match_data['input']['category'] = 'movie'  # Propagated by executor
  
  Group 1 (parallel):
    tmdb.execute(match_data)
      -> Reads: match_data['renamer']['parsed']['movie']
      -> Reads: match_data['ffprobe']['container']['duration'] (for validation)
      -> match_data['tmdb'] = {movie: {...}, validation: {...}}
    
    tvdb.execute(match_data)
      -> match_data['tvdb'] = {movie: {...}}
    
    omdb.execute(match_data)
      -> match_data['omdb'] = {movie: {...}}

Final match_data:
  {
    'input': {'path': '/file.mkv', 'category': 'movie'},
    'ffprobe': {...},
    'renamer': {...},
    'tmdb': {...},
    'tvdb': {...},
    'omdb': {...}
  }
```

---

## PLUGIN VALIDATION SYSTEM

All output plugins inherit `_validate_duration()` from `OutputPlugin`:

```python
# In plugin execute():
validation_result = self._validate_duration(
    actual_seconds=ffprobe_data['container']['duration'],
    expected_minutes=api_result['runtime'],
    tolerance_seconds=600
)

result['validation'] = {
    'tests_passed': validation_result.tests_passed,
    'tests_total': validation_result.tests_total,
    'details': validation_result.details
}
```

**Core does NOT aggregate validations** - Each plugin manages its own in `plugin.globals.validation`.

---

This completes Plugin documentation. All 8 plugins detailed with implementations, logic flows, API structures, and communication patterns.
