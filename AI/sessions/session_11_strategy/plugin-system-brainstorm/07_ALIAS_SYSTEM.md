# ALIAS SYSTEM

```yaml
tarih: 2025-12-02
durum: final
```

---

## 1. CURRENT

```yaml
# config.yml (mevcut)
aliases:
  m: "match"
  g: "globals"
  movie: "renamer.parsed.movie"
```

Sorunlar:
- Magic path (tmdb.movie direkt erisim)
- Belirsiz scope
- Sistem vs kullanici alias ayrimi yok

---

## 2. FEATURE

```yaml
# config.yml (yeni)
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show

# Template'de kullanim
{{ m.title }}

# Veya inline Jinja2
{% set m = job.plugins.tmdb.movie %}
{{ m.title }}
```

---

## 3. WHY

### Felsefe

```
+----------------------------------------------------------+
|              ALIAS FELSEFESI                              |
+----------------------------------------------------------+
|                                                           |
|  SORU: Magic path olacak mi?                             |
|  CEVAP: HAYIR                                            |
|                                                           |
|  YANLIS (magic):                                          |
|  {{ tmdb.movie.title }}                                  |
|                                                           |
|  DOGRU (explicit):                                        |
|  {{ job.plugins.tmdb.movie.title }}                      |
|                                                           |
|  NEDEN:                                                   |
|  - Explicit is better than implicit (Zen of Python)      |
|  - Debuggability: Tam path gorunur                       |
|  - No ambiguity: tmdb config mi data mi?                 |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. SCHEMA

### DEFAULT ALIAS (Sistem Inject)

```
+----------------------------------------------------------+
|              SISTEM TARAFINDAN INJECT EDILEN             |
+----------------------------------------------------------+
|  ALIAS          SOURCE              ACIKLAMA              |
+----------------------------------------------------------+
|  job            GlobalState         Current job state    |
|  jobs           GlobalState         Tum job'lar          |
|  run            GlobalState         Run state            |
|  provides       ProvideRegistry     Tamamlanan provides  |
|  events         EventBus.history    Emit edilen events   |
|  config         ConfigLoader        Config degerleri     |
+----------------------------------------------------------+

Bu alias'lar OTOMATIK inject edilir.
Kullanici tanimlama GEREKSIZ.
Override edilemez.
```

### KULLANICI ALIAS (config.yml)

```yaml
# config.yml
aliases:
  # Provides shortcut
  p: provides
  
  # Job data shortcuts  
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  r: job.plugins.renamer.parsed
```

### INLINE ALIAS (Jinja2)

```jinja2
{% set m = job.plugins.tmdb.movie %}
{% set year = m.release_date[:4] %}
{{ m.title }} ({{ year }})
```

### PRIORITY

```
1. Inline (Jinja2 set)      YUKSEK
2. User (config.aliases)
3. System (inject)          DUSUK
```

### Resolution Flow

```
              ALIAS RESOLUTION

+----------------------------------------------------------+
|  Template: "{{ m.title }}"                               |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  1. Check inline alias (Jinja2 set)                      |
|     --> Not found                                        |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  2. Check user alias (config.aliases)                    |
|     m -> job.plugins.tmdb.movie                          |
|     --> Found!                                           |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  3. Expand path                                          |
|     job.plugins.tmdb.movie.title                         |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  4. Resolve value                                        |
|     --> "Inception"                                      |
+----------------------------------------------------------+
```

---

## 5. CONFIG ALIASES

```yaml
# config.yml
aliases:
  # TMDb shortcuts
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  
  # Renamer shortcuts
  p: job.plugins.renamer.parsed
  movie: job.plugins.renamer.parsed.movie
  show: job.plugins.renamer.parsed.show
  
  # FFProbe shortcuts
  video: job.plugins.ffprobe.video
  audio: job.plugins.ffprobe.audio
```

### Kullanim

```jinja2
{# Uzun yol #}
{{ job.plugins.tmdb.movie.title }}

{# User alias ile #}
{{ m.title }}

{# Renamer alias ile #}
{{ movie.name }} ({{ movie.year }})

{# Nested alias #}
{% set genres = m.genres | join(', ') %}
{{ m.title }} - {{ genres }}
```

---

## 6. INLINE ALIASES

```jinja2
{# Template icinde tanimlama #}
{% set m = job.plugins.tmdb.movie %}
{% set r = job.plugins.renamer.parsed.movie %}

{# Kullanim #}
{{ m.title }} ({{ m.release_date[:4] }})
Original: {{ r.name }}

{# Kompleks alias #}
{% set year = m.release_date[:4] if m.release_date else 'Unknown' %}
{% set quality = job.input.path | regex_search('(\d{3,4}p)') %}

{{ m.title }} ({{ year }}) [{{ quality }}]
```

---

## 7. PRIORITY

```
              ALIAS PRIORITY

1. Inline alias (Jinja2 set)      [En yuksek]
2. User alias (config.aliases)
3. Short alias (j, r, o)
4. System alias (job, run, ...)   [En dusuk]

ORNEK:
  # config.yml
  aliases:
    job: something.else    # GECERSIZ! System alias override edilemez
    
  SONUC: Hata verilir
```

---

## 8. VALIDATION

```
+----------------------------------------------------------+
|              ALIAS VALIDATION                             |
+----------------------------------------------------------+
|                                                           |
|  1. System alias override edilemez                       |
|     aliases:                                             |
|       job: xxx     # ERROR                               |
|       run: xxx     # ERROR                               |
|                                                           |
|  2. Short alias override edilebilir                      |
|     aliases:                                             |
|       j: xxx       # OK (ama onerılmez)                  |
|                                                           |
|  3. Path syntax kontrolu                                 |
|     aliases:                                             |
|       m: job.plugins.tmdb.movie    # OK                  |
|       m: tmdb.movie                # WARN (magic path)   |
|                                                           |
|  4. Circular reference kontrolu                          |
|     aliases:                                             |
|       a: b         # ERROR if b -> a                     |
|       b: a                                               |
|                                                           |
+----------------------------------------------------------+
```

---

## 9. IMPLEMENTATION

```python
class AliasResolver:
    SYSTEM_ALIASES = {'job', 'jobs', 'run', 'options', 'index'}
    SHORT_ALIASES = {'j': 'job', 'r': 'run', 'o': 'options'}
    
    def __init__(self, user_aliases: Dict[str, str]):
        self._user_aliases = user_aliases
        self._validate()
    
    def _validate(self):
        for name in self._user_aliases:
            if name in self.SYSTEM_ALIASES:
                raise ValueError(f"Cannot override system alias: {name}")
    
    def resolve(self, name: str) -> str:
        # Priority: user > short > system
        if name in self._user_aliases:
            return self._user_aliases[name]
        if name in self.SHORT_ALIASES:
            return self.SHORT_ALIASES[name]
        return name
    
    def build_context(self, base_context: Dict) -> Dict:
        """Alias'lari context'e ekle"""
        context = dict(base_context)
        
        # Short aliases
        context['j'] = context.get('job')
        context['r'] = context.get('run')
        context['o'] = context.get('options')
        
        # User aliases (path resolve)
        for alias, path in self._user_aliases.items():
            context[alias] = self._resolve_path(context, path)
        
        return context
    
    def _resolve_path(self, context: Dict, path: str) -> Any:
        """Dot-notation path'i resolve et"""
        parts = path.split('.')
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

Not: Direkt execution'da kullanilmaz, sadece
pattern gosterimi icin yazilmistir.
```

---

## 10. TEMPLATE MANAGER UPDATE

```python
class TemplateManager:
    def __init__(self, config: Dict):
        self._aliases = AliasResolver(config.get('aliases', {}))
        self._env = jinja2.Environment(...)
    
    def render(self, template: str, context: Dict) -> str:
        # Alias'lari context'e ekle
        full_context = self._aliases.build_context(context)
        
        # Render
        return self._env.from_string(template).render(full_context)

Not: Direkt execution'da kullanilmaz, sadece
pattern gosterimi icin yazilmistir.
```

---

## 11. ORNEK TEMPLATE

```yaml
# config.yml
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  r: job.plugins.renamer.parsed

tasks:
  - name: movie_output
    type: save
    condition: "{{ r.movie }}"
    destination: |
      {% set year = m.release_date[:4] if m.release_date else 'Unknown' %}
      /media/movies/{{ m.title }} ({{ year }})/{{ r.movie.name }}.{{ job.input.path | ext }}
      
  - name: show_output
    type: save
    condition: "{{ r.show }}"
    destination: |
      {% set show = s %}
      /media/shows/{{ show.name }}/Season {{ '%02d' | format(r.show.season) }}/{{ r.show.name }}.{{ job.input.path | ext }}
```

---

## 12. MIGRATION

```
MEVCUT:
  aliases:
    m: "match"
    g: "globals"
    movie: "renamer.parsed.movie"

YENI:
  aliases:
    j: job                            # short alias (sistem)
    m: job.plugins.tmdb.movie         # user alias
    movie: job.plugins.renamer.parsed.movie
    
NOT: Eski "match", "globals" aliasları
job ve run olarak degistirildi.
```
