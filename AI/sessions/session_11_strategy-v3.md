# SESSION 11 STRATEGY v3 - FINAL

```yaml
date: 2025-11-28
type: strategy
status: completed
previous_session: 10
focus: Unified Nested State + 3 System Aliases + Relaxed Validation
analyst: Strategy Chat
```

---

## DEĞİŞİKLİK ÖZETİ (v2 → v3)

| Konu | v2 | v3 |
|------|----|----|
| MongoDB table | `plugin_results` | `plugins` |
| Sistem aliases | `execution`, `match` | `execution`, `match`, `matches` |
| matches konumu | `execution.matches` | Root'ta ayrı `matches` (RAM opt) |
| Input plugin zorunluluğu | Zorunlu | Opsiyonel |
| Output plugin bağımlılığı | Input'a bağlı | Bağımsız olabilir (dependency yani expects kısmı)

---

## YENİ STATE YAPISI

### Global Context (Template Rendering İçin)

```python
# ROOT LEVEL - 3 SİSTEM ALIAS'I
{
    # 1. EXECUTION - Mevcut çalışma bilgisi
    'execution': {
        'id': 'abc123',
        'status': {
            'success': True,
            'total_matches': 2,
            'completed': 2,
            'failed': 0,
            'started_at': '2025-11-28T12:00:00',
            'finished_at': '2025-11-28T12:01:00',
            'duration_ms': 60000
        },
        'config': {
            'options': {'debug': True, 'dry_run': True},
            'plugins': {...},
            'tasks': [...]
        }
    },
    
    # 2. MATCH - Şu an işlenen match (current)
    'match': {
        'index': 0,
        'input': {
            'path': '/path/to/file.mkv',
            'category': 'movie',
            'virtual': False
        },
        'status': {
            'success': True,
            'executed_plugins': ['scanner', 'ffprobe', 'renamer', 'tmdb'],
            'failed_plugins': [],
            'started_at': '...',
            'duration_ms': 2500
        },
        'output': {
            'tasks': [
                {'name': 'print_header', 'success': True, 'rendered': '...'}
            ]
        },
        'plugins': {
            'scanner': {...},
            'ffprobe': {...},
            'renamer': {...},
            'tmdb': {...}
        }
    },
    
    # 3. MATCHES - Tüm match'ler (summary taskler için)
    # NOT: execution.matches DEĞİL, root'ta ayrı (RAM optimizasyonu)
    'matches': [
        {
            'index': 0,
            'input': {...},
            'status': {...},
            'plugins': {...}
        },
        {
            'index': 1,
            'input': {...},
            'status': {...},
            'plugins': {...}
        }
    ]
}
```

### Template Kullanımı

```jinja2
{# Execution bilgisi #}
{{ execution.id }}
{{ execution.status.total_matches }}
{{ execution.config.options.debug }}

{# Current match #}
{{ match.index }}
{{ match.input.path }}
{{ match.input.category }}
{{ match.plugins.tmdb.movie.title }}
{{ match.plugins.renamer.parsed.movie.name }}

{# Summary task - tüm matchlere erişim #}
{% for m in matches %}
  Match {{ m.index }}: {{ m.plugins.renamer.parsed.movie.name }}
{% endfor %}

{# Indexed access #}
{{ matches[0].plugins.tmdb.movie.title }}
```

---

## MONGODB YAPISI

### Collection: `executions`

```javascript
{
  _id: ObjectId("..."),
  id: "abc123",
  branch_id: ObjectId("..."),
  
  status: {
    success: true,
    total_matches: 2,
    completed: 2,
    failed: 0,
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 60000
  },
  
  config: {
    options: {debug: true, dry_run: true},
    plugins: {
      scanner: {enabled: true, targets: [...]},
      tmdb: {enabled: true, language: "tr-TR"}
    },
    tasks: [...]
  },
  
  created_at: ISODate("...")
}
```

### Collection: `matches`

```javascript
{
  _id: ObjectId("..."),
  execution_id: "abc123",
  index: 0,
  
  input: {
    path: "/path/to/file.mkv",
    category: "movie",
    virtual: false
  },
  
  status: {
    success: true,
    executed_plugins: ["scanner", "ffprobe", "renamer", "tmdb"],
    failed_plugins: [],
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 2500
  },
  
  output: {
    tasks: [
      {name: "print_header", success: true, rendered: "...", type : "print"}
    ]
  },
  
  created_at: ISODate("...")
}
```

### Collection: `plugins` (ESKİ: plugin_results)

```javascript
{
  _id: ObjectId("..."),
  execution_id: "abc123",
  match_index: 0,
  plugin_name: "tmdb",
  
  status: {
    success: true,
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 800
  },
  
  // Plugin-specific data (core'a opaque)
  data: {
    movie: {
      id: 1234,
      title: "Mr. & Mrs. Smith",
      year: 2005,
      genres: ["Action", "Comedy"]
    }
  },
  
  created_at: ISODate("...")
}
```

---

## VALIDATION KURALLARI DEĞİŞİKLİĞİ

### Kaldırılan Kurallar

```python
# ESKİ (KALDIRILACAK) - Input plugin zorunlu değil artık
if not any(p.category == 'input' for p in plugins):
    raise ValueError("At least one input plugin must be enabled")
```

### Yeni Davranış

1. **Input plugin yoksa**: Sistem yine de çalışır, sadece match olmaz
2. **Output plugin input'a bağlı değil**: `depends_on: []` ile bağımsız output plugin olabilir
3. **Validation = Sadece hata tespiti**: Çalışmayı engellemez, sadece loglar

```python
# YENİ - Sistem her zaman çalışır
def validate_plugins(plugins: List[PluginManifest]) -> List[str]:
    """Validate plugins and return warnings (not errors)"""
    warnings = []
    
    input_plugins = [p for p in plugins if p.category == 'input']
    if not input_plugins:
        warnings.append("No input plugins enabled - no matches will be found")
    
    return warnings
```

---

## EXECUTION PLAN (DETAYLI)

### Phase 1: State Models Refactor

**Dosya:** `src/archiverr/state/models.py`

**Mevcut Durum (lines 22-60):**
```python
@dataclass
class ExecutionState:
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
```

**Yeni Yapı:**
```python
@dataclass
class ExecutionStatus:
    """Nested status object"""
    success: bool = True
    total_matches: int = 0
    completed: int = 0
    failed: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

@dataclass
class ExecutionState:
    """Execution-level state with nested structure"""
    id: str
    status: ExecutionStatus = field(default_factory=ExecutionStatus)
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'status': {
                'success': self.status.success,
                'total_matches': self.status.total_matches,
                'completed': self.status.completed,
                'failed': self.status.failed,
                'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
                'finished_at': self.status.finished_at.isoformat() if self.status.finished_at else None,
                'duration_ms': self.status.duration_ms
            },
            'config': self.config
        }
```

**Mevcut MatchState (lines 92-169):**
```python
@dataclass
class MatchState:
    index: int
    input_path: str
    execution_id: str
    success: bool = True
    # ... flat fields
```

**Yeni MatchState:**
```python
@dataclass
class MatchInput:
    """Match input info"""
    path: str
    category: str = "unknown"
    virtual: bool = False

@dataclass
class MatchStatus:
    """Match status info"""
    success: bool = True
    executed_plugins: List[str] = field(default_factory=list)
    failed_plugins: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

@dataclass
class MatchOutput:
    """Match output info"""
    tasks: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class MatchState:
    """Per-match state with nested structure"""
    index: int
    execution_id: str
    input: MatchInput = field(default_factory=lambda: MatchInput(path=""))
    status: MatchStatus = field(default_factory=MatchStatus)
    output: MatchOutput = field(default_factory=MatchOutput)
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'input': {
                'path': self.input.path,
                'category': self.input.category,
                'virtual': self.input.virtual
            },
            'status': {
                'success': self.status.success,
                'executed_plugins': self.status.executed_plugins,
                'failed_plugins': self.status.failed_plugins,
                'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
                'finished_at': self.status.finished_at.isoformat() if self.status.finished_at else None,
                'duration_ms': self.status.duration_ms
            },
            'output': {
                'tasks': self.output.tasks
            },
            'plugins': self.plugins
        }
```

---

### Phase 2: State Manager Refactor

**Dosya:** `src/archiverr/state/manager.py`

**Mevcut (lines 398-488):** İki ayrı fonksiyon var:
- `build_template_context()` - Jinja2 için
- `build_api_response_for_templates()` - API response için

**SİLİNECEK:** Her iki fonksiyon da silinecek.

**YENİ FONKSİYON:**
```python
def get_context(self, match_index: Optional[int] = None) -> Dict[str, Any]:
    """
    Build unified context for templates.
    
    Returns 3 root-level objects:
    - execution: Current execution state
    - match: Current match (if match_index provided)
    - matches: All matches (for summary tasks)
    
    Args:
        match_index: Current match index (None for execution-only context)
        
    Returns:
        Unified context dict
    """
    context = {
        # 1. EXECUTION
        'execution': self._execution.to_dict() if self._execution else {},
        
        # 3. MATCHES (always included for summary access)
        'matches': [
            m.to_dict() for m in sorted(self._matches.values(), key=lambda x: x.index)
        ]
    }
    
    # 2. MATCH (only if processing specific match)
    if match_index is not None and match_index in self._matches:
        context['match'] = self._matches[match_index].to_dict()
    
    return context
```

**DEĞİŞTİRİLECEK SATIRLAR:**

`register_match()` (lines 246-285):
```python
# ESKİ
match = MatchState(
    index=index,
    input_path=input_path,
    execution_id=self._execution.id,
    started_at=datetime.now(),
    status=ExecutionStatus.RUNNING
)

# YENİ
match = MatchState(
    index=index,
    execution_id=self._execution.id,
    input=MatchInput(path=input_path),
    status=MatchStatus(started_at=datetime.now())
)
```

`update_plugin_result()` (lines 295-335):
```python
# ESKİ - match.add_plugin_result() kullanıyor
match.add_plugin_result(plugin_name, result)

# YENİ - Doğrudan nested update
match.plugins[plugin_name] = result.to_dict()
if result.success:
    match.status.executed_plugins.append(plugin_name)
else:
    match.status.failed_plugins.append(plugin_name)
    match.status.success = False
```

---

### Phase 3: Template Manager Simplify

**Dosya:** `src/archiverr/core/tasks/template_manager.py`

**Mevcut (lines 125-242):** Karmaşık context building + magic plugin injection

**SİLİNECEK (lines 206-210):**
```python
# Magic plugin injection - KALDIRILACAK
for plugin_name, plugin_data in match_plugins.items():
    jinja_context[plugin_name] = plugin_data
```

**YENİ `render()` metodu:**
```python
def render(self, template: str, context: Dict[str, Any], current_index: int = 0) -> str:
    """
    Render template with unified context.
    
    Context structure:
    - execution: {...}
    - match: {...}  
    - matches: [...]
    
    NO MAGIC INJECTION. Access plugins via match.plugins.X
    
    Args:
        template: Jinja2 template string
        context: Unified context from state.get_context()
        current_index: Current match index (for backward compat)
    """
    # Process template functions (index:, count:)
    processed = self._process_functions(template, context, current_index)
    
    # Convert $ syntax to Jinja2 (backward compat)
    processed = self._process_dollar_syntax(processed)
    
    try:
        tmpl = self.env.from_string(processed)
        return tmpl.render(**context)
    except Exception as e:
        return f"Template error: {e}"
```

**SİLİNECEK:** `DEFAULT_ALIASES` dictionary (lines 28-32)
```python
# KALDIRILACAK - Artık sistem alias'ları yok (execution, match, matches zaten root'ta)
DEFAULT_ALIASES = {
    'e': 'execution',
    'm': 'match',
    'g': 'globals',
}
```

---

### Phase 4: Persistence Layer Update

**Dosya:** `src/archiverr/infrastructure/persistence/mock_persistence.py`

**Collection adı değişikliği:**
```python
# ESKİ
self._plugin_results = {}

# YENİ
self._plugins = {}
```

**Metod güncellemesi:**
```python
# ESKİ
def save_plugin_result(self, execution_id, match_index, plugin_name, data):
    key = f"{execution_id}_{match_index}_{plugin_name}"
    self._plugin_results[key] = data

# YENİ
def save_plugin(self, execution_id, match_index, plugin_name, data):
    key = f"{execution_id}_{match_index}_{plugin_name}"
    self._plugins[key] = data
```

---

### Phase 5: Validation Relaxation

**Dosya:** `src/archiverr/__main__.py`

**Mevcut (yaklaşık lines 160-180):**
```python
# Phase 4: Execute input plugins
debugger.debug("system", "Executing input plugins")
executor = PluginExecutor()
# ...
input_matches = executor.execute_inputs(input_plugins)

if not input_matches:
    debugger.warn("executor", "No matches found")
    sys.exit(0)  # ← BU KALDIRILACAK
```

**YENİ:**
```python
# Phase 4: Execute input plugins (if any)
input_plugins = {name: p for name, p in plugins.items() if is_input_plugin(p)}

if not input_plugins:
    debugger.info("system", "No input plugins enabled - creating empty execution")
    input_matches = []
else:
    debugger.debug("system", "Executing input plugins")
    input_matches = executor.execute_inputs(input_plugins)

if not input_matches:
    debugger.info("executor", "No matches found - completing execution")
    # DON'T EXIT - Let execution complete normally with 0 matches
```

---

### Phase 6: Tests

**Yeni Test Dosyaları:**

`tests/unit/state/test_models.py`:
```python
def test_execution_state_to_dict():
    """Test nested ExecutionState serialization"""
    state = ExecutionState(id="test123")
    state.status.success = True
    state.status.total_matches = 5
    
    result = state.to_dict()
    
    assert result['id'] == "test123"
    assert result['status']['success'] == True
    assert result['status']['total_matches'] == 5

def test_match_state_to_dict():
    """Test nested MatchState serialization"""
    state = MatchState(
        index=0,
        execution_id="test123",
        input=MatchInput(path="/path/file.mkv", category="movie")
    )
    
    result = state.to_dict()
    
    assert result['index'] == 0
    assert result['input']['path'] == "/path/file.mkv"
    assert result['input']['category'] == "movie"
```

`tests/unit/state/test_manager.py`:
```python
def test_get_context_with_match():
    """Test unified context building"""
    manager = StateManager()
    manager.start_execution({})
    manager.register_match(0, "/path/file.mkv")
    
    context = manager.get_context(match_index=0)
    
    assert 'execution' in context
    assert 'match' in context
    assert 'matches' in context
    assert context['match']['index'] == 0

def test_get_context_without_match():
    """Test context for summary tasks (no specific match)"""
    manager = StateManager()
    manager.start_execution({})
    manager.register_match(0, "/path/a.mkv")
    manager.register_match(1, "/path/b.mkv")
    
    context = manager.get_context()
    
    assert 'execution' in context
    assert 'match' not in context  # No specific match
    assert len(context['matches']) == 2
```

`tests/unit/core/test_template_manager_v3.py`:
```python
def test_render_with_nested_context():
    """Test rendering with new nested context"""
    tm = TemplateManager()
    
    context = {
        'execution': {'id': 'abc', 'status': {'total_matches': 2}},
        'match': {
            'index': 0,
            'input': {'path': '/test.mkv'},
            'plugins': {
                'tmdb': {'movie': {'title': 'Test Movie'}}
            }
        },
        'matches': []
    }
    
    result = tm.render("{{ match.plugins.tmdb.movie.title }}", context)
    assert result == "Test Movie"

def test_no_magic_injection():
    """Verify plugin data is NOT injected at root"""
    tm = TemplateManager()
    
    context = {
        'execution': {},
        'match': {
            'plugins': {'tmdb': {'movie': {'title': 'Test'}}}
        },
        'matches': []
    }
    
    # Old magic syntax should NOT work
    result = tm.render("{{ tmdb.movie.title }}", context)
    assert "Test" not in result  # Should fail or be empty
```

---

## DOSYA DEĞİŞİKLİKLERİ ÖZETİ

| Dosya | Değişiklik | Satırlar |
|-------|------------|----------|
| `state/models.py` | Nested dataclasses | ~100 satır yeniden yazım |
| `state/manager.py` | `get_context()` + eski fonksiyonlar sil | ~150 satır |
| `core/tasks/template_manager.py` | Simplify render() | ~80 satır |
| `infrastructure/persistence/*.py` | Collection rename | ~20 satır |
| `__main__.py` | Validation relaxation | ~15 satır |
| `tests/unit/state/test_models.py` | YENİ | ~50 satır |
| `tests/unit/state/test_manager.py` | YENİ | ~80 satır |
| `tests/unit/core/test_template_manager_v3.py` | YENİ | ~60 satır |

---

## MİGRASYON NOTU

### Breaking Changes

1. **Template syntax değişiyor:**
   ```jinja2
   {# ESKİ #}
   {{ tmdb.movie.title }}
   {{ globals.status.matches }}
   {{ match_globals.input.path }}
   
   {# YENİ #}
   {{ match.plugins.tmdb.movie.title }}
   {{ execution.status.total_matches }}
   {{ match.input.path }}
   ```

2. **config.yml templates güncellenmeli**

3. **MongoDB collection adı değişiyor:** `plugin_results` → `plugins`

---

## KRİTİK NOTLAR

1. **3 Sistem Alias:** `execution`, `match`, `matches` - Başka alias YOK
2. **matches RAM'de ayrı:** `execution.matches` değil, root'ta
3. **Magic injection YOK:** `{{ tmdb.movie }}` çalışmaz, `{{ match.plugins.tmdb.movie }}` kullan
4. **Validation = Warning:** Input plugin yoksa çalışmaya devam et
5. **Output bağımsız olabilir:** `depends_on: []` ile input'tan bağımsız output plugin

---

**Tahmini Süre:** 5-6 saat

**Bu strateji Session 11 Execution Chat için hazırlandı.**
**Tarih:** 2025-11-28
