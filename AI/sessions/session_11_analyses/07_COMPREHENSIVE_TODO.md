# SESSION 11 KAPSAMLI TODO LİSTESİ

```yaml
tarih: 2025-12-04
versiyon: final
kaynak: 
  - HUMAN/FINAL_DATASETS.yml
  - AI/sessions/session_11_strategy/*
  - AI/PHILOSOPHY.md
  - Kullanıcı geri bildirimleri
```

---

## ✅ TAMAMLANAN GÖREVLER

### Bu Oturumda Tamamlananlar

| # | Görev | Dosya | Durum |
|---|-------|-------|-------|
| 1 | SYSTEM_ALIASES 8 adete düşürüldü | `alias_resolver.py` | ✅ |
| 2 | SHORT_ALIASES kaldırıldı (boş dict) | `alias_resolver.py` | ✅ |
| 3 | DEFAULT_ALIASES kaldırıldı (TemplateManager) | `template_manager.py` | ✅ |
| 4 | 8 sistem alias'ı jinja_context'e eklendi | `template_manager.py` | ✅ |
| 5 | `config` alias çalışıyor | `template_manager.py` | ✅ |
| 6 | `options` alias çalışıyor | `template_manager.py` | ✅ |
| 7 | `plugins` alias çalışıyor | `template_manager.py` | ✅ |
| 8 | `job.plugins.*` erişimi çalışıyor | `template_manager.py` | ✅ |
| 9 | Renamer provides güncellendi | `renamer/manifest.yml` | ✅ |
| 10 | TMDb provides güncellendi | `tmdb/manifest.yml` | ✅ |
| 11 | Tasker requires eklendi | `tasker/manifest.yml` | ✅ |
| 12 | Mevcut workflow şeması oluşturuldu | `04_CURRENT_*.md` | ✅ |
| 13 | Hedef workflow şeması oluşturuldu | `05_TARGET_*.md` | ✅ |
| 14 | Jinja2 kullanım kılavuzu oluşturuldu | `06_JINJA2_*.md` | ✅ |

---

## P0: KRİTİK (Fonksiyonel Hatalar)

| # | Görev | Açıklama | Tahmini Süre |
|---|-------|----------|--------------|
| - | Şu an kritik hata YOK | - | - |

---

## P1: YÜKSEK (Strateji Uyumsuzlukları) ✅ TAMAMLANDI

| # | Görev | Açıklama | Dosya | Durum |
|---|-------|----------|-------|-------|
| 1 | `provides` alias'ını inject et | Aktif provides registry'yi template context'e ekle | `template_manager.py`, `stage_executor.py` | ✅ |
| 2 | `events` alias'ını inject et | Event bus history'yi template context'e ekle | `template_manager.py`, `events/bus.py` | ✅ |
| 3 | Provides completion sistemi | `services.provides.complete()` metodu implement et | `services/provides_service.py` | ✅ |
| 4 | Requires prefix validation | `provides.*`, `job.*`, `events.*` prefix zorunlu | `requires_validator.py` | ✅ |

---

## P2: ORTA (İyileştirmeler) - Kısmen Tamamlandı

| # | Görev | Açıklama | Dosya | Durum |
|---|-------|----------|-------|-------|
| 1 | Manifest içinde alias/Jinja2 | Manifest'te `{{ }}` kullanımı | `discovery.py` | ✅ |
| 2 | Conflict detection | Lockable provides için çakışma tespiti | `startup_validator.py` | ✅ |
| 3 | Legacy kod temizliği | `execution_service.py`, eski alias'lar | Çeşitli | 📋 |
| 4 | Failing testler düzeltmesi | 13 adet test hatası | `tests/unit/core/` | 📋 |
| 5 | Template-Alias entegrasyonu | İki ayrı sistem birleştirilmeli | `alias_resolver.py`, `template_manager.py` | 📋 |

---

## P3: DÜŞÜK (Gelecek İyileştirmeler)

| # | Görev | Açıklama | Dosya | Tahmini Süre |
|---|-------|----------|-------|--------------|
| 1 | Reactive plugin sistemi | `reactive: true` implementasyonu | `stage_executor.py` | 4 saat |
| 2 | Plugin signature audit | Tüm plugin'leri yeni signature'a geçir | `plugins/*/client.py` | 2 saat |
| 3 | Error codes dokümantasyonu | E001-E023 açıklamaları | `docs/ERROR_CODES.md` | 1 saat |
| 4 | Performance benchmarks | 1000+ dosya senaryosu testleri | `tests/benchmark/` | 3 saat |
| 5 | Memory usage tracking | Plugin data cache metrikleri | `memory/` | 2 saat |

---

## DETAYLI GÖREV AÇIKLAMALARI

### P1.1: Provides Alias Inject

**Sorun:** `{{ provides }}` template'te boş dict dönüyor.

**Çözüm:**
```python
# stage_executor.py - provides registry oluştur
provides_registry = ProvidesRegistry()
for plugin in executed_plugins:
    for provide in plugin.manifest.provides:
        provides_registry.register(plugin.name, provide, status="completed")

# template_manager.py - inject et
jinja_context['provides'] = provides_registry.to_dict()
```

**Beklenen Çıktı:**
```jinja2
{{ provides }}
# {'http.request': {'tmdb': 'completed'}, 'fs.read': {'scanner': 'completed'}}

{{ provides.http.request.tmdb }}
# 'completed'
```

---

### P1.2: Events Alias Inject

**Sorun:** `{{ events }}` template'te boş dict dönüyor.

**Çözüm:**
```python
# event_bus.py - history tutma
class EventBus:
    def __init__(self):
        self._history = []
    
    def emit(self, event_name, data):
        self._history.append({
            'event': event_name,
            'data': data,
            'timestamp': datetime.now()
        })
        # ... emit logic

# template_manager.py - inject et
jinja_context['events'] = event_bus.get_history()
```

---

### P1.3: Provides Completion Sistemi

**Sorun:** Plugin'ler provides'larını erken tamamlayamıyor.

**Çözüm:**
```python
# services/protocols.py
class ProvidesService(Protocol):
    def complete_provide(self, provide: str) -> None:
        """Mark a specific provide as completed early"""
        ...

# Plugin kullanımı
class TMDbPlugin:
    def execute(self, job, services):
        response = self.fetch_metadata(job)
        services.provides.complete("http.request")  # Erken tamamla
        
        self.download_artwork(response)  # Yavaş işlem
        services.provides.complete("fs.write")
        
        return PluginResult.success(response)
```

---

### P2.1: Manifest İçinde Alias/Jinja2

**Sorun:** Manifest'te `{{ }}` kullanılamıyor.

**Çözüm:**
```python
# plugin_registry.py - manifest yüklerken
def load_manifest(self, path):
    with open(path) as f:
        raw = yaml.safe_load(f)
    
    # Manifest-level aliases
    aliases = raw.get('aliases', {})
    
    # Jinja2 ile render et
    env = Environment()
    for key in ['requires', 'provides']:
        if key in raw:
            raw[key] = [
                env.from_string(item).render(**aliases, **self._global_context)
                for item in raw[key]
            ]
    
    return raw
```

**Kullanım:**
```yaml
# manifest.yml
aliases:
  renamer_parsed: job.plugins.renamer.parsed

requires:
  - "{{ renamer_parsed }}"
```

---

### P2.2: Conflict Detection

**Sorun:** Lockable provides (fs.write) için çakışma tespiti yok.

**Çözüm:**
```python
# validation/conflict_detector.py
LOCKABLE = ['fs.write', 'fs.delete', 'fs.move', 'fs.hardlink', 'fs.symlink']

def detect_conflicts(plugins):
    conflicts = []
    
    provides_map = {}  # provide:path → [plugin1, plugin2]
    
    for plugin in plugins:
        for provide in plugin.manifest.provides:
            base, *path = provide.split(':')
            if base in LOCKABLE:
                key = provide
                if key not in provides_map:
                    provides_map[key] = []
                provides_map[key].append(plugin.name)
    
    for provide, plugins in provides_map.items():
        if len(plugins) > 1:
            conflicts.append({
                'provide': provide,
                'plugins': plugins,
                'severity': 'error'
            })
    
    return conflicts
```

---

## PRİORİTE TABLOSU

| Öncelik | Görev Sayısı | Toplam Süre |
|---------|--------------|-------------|
| P1 | 4 | ~8 saat |
| P2 | 5 | ~12 saat |
| P3 | 5 | ~12 saat |
| **TOPLAM** | **14** | **~32 saat** |

---

## SONRAKİ ADIMLAR

1. **Hemen (P1):**
   - provides ve events alias inject
   - Provides completion sistemi
   - Requires prefix validation

2. **Bu Hafta (P2):**
   - Manifest Jinja2 desteği
   - Conflict detection
   - Legacy kod temizliği

3. **Gelecek Sprint (P3):**
   - Reactive plugin sistemi
   - Performance benchmarks

---

**Son Güncelleme:** 2025-12-04
