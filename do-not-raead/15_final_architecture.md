# FINAL ARCHITECTURE SPEC

```yaml
date: 2025-12-02
type: technical-spec
status: ready-for-execution
```

---

# 1. MEVCUT DURUM

## 1.1 Kod Analizi

| Dosya | Satır | Durum |
|-------|-------|-------|
| `events/bus.py` | 286 | EventBus mevcut, çalışıyor |
| `events/handlers.py` | 221 | Handler'lar mevcut |
| `state/manager.py` | 594 | StateManager mevcut, event emit ediyor |
| `core/plugins/executor.py` | 414 | PluginExecutor mevcut |
| `core/plugins/resolver.py` | ~100 | Topological sort mevcut |
| `core/plugins/loader.py` | - | Manifest validation eksik |

## 1.2 Mevcut Event'ler (events/bus.py:Events)

```
execution.started, execution.completed, execution.failed
match.started, match.completed, match.failed
plugin.started, plugin.completed, plugin.failed, plugin.skipped
task.started, task.completed, task.failed
state.changed
db.connected, db.disconnected, db.synced, db.error
validation.passed, validation.failed
```

## 1.3 Eksikler

| Eksik | Açıklama |
|-------|----------|
| JobState dataclass | Her job için merkezi state objesi |
| Provides constants | Sistem tarafından tanınan provides listesi |
| Manifest validation | provides/on değerlerinin kontrolü |
| provides tracking | Plugin bittiğinde provides emit |
| after logic | provides-based ordering |
| on subscription | Event-based plugin trigger |

---

# 2. HEDEF MİMARİ

## 2.1 JobState

```python
@dataclass
class JobState:
    input: InputData        # scanner
    parsed: ParsedData      # renamer
    metadata: MetadataData  # tmdb/tvdb
    output: OutputData      # tasker
    plugins: Dict[str, Any] # plugin-specific data
```

## 2.2 Stage Flow

```
input --> parse --> metadata --> output
  |         |          |           |
scanner  renamer    tmdb/tvdb    tasker
```

## 2.3 Provides (9 değer - sabit liste)

```
input.files
parsed.movie, parsed.show, parsed.unknown
metadata.movie, metadata.show
output.moved, output.copied, output.linked
```

## 2.4 Events (sistem emit eder)

```
execution.started, execution.completed, execution.failed
job.started, job.completed, job.failed, job.skipped
stage.started, stage.completed
plugin.started, plugin.completed, plugin.failed, plugin.skipped
provide.available, provide.all_done
state.changed
```

## 2.5 Manifest Schema

```yaml
name: string
version: string
stage: input | parse | metadata | output
mode: per_job | per_run

provides: [string]  # Provides listesinden
requires: [string]  # Data path
after: [string]     # Provides-based ordering
depends: [string]   # Plugin name
on: [string]        # Event subscription
```

---

# 3. DEĞİŞİKLİK LİSTESİ

## 3.1 Yeni Dosyalar

| Dosya | İçerik |
|-------|--------|
| `core/constants.py` | Provides, Events constant class'ları |
| `state/models.py` | JobState, InputData, ParsedData vb. dataclass'lar |

## 3.2 Güncellenecek Dosyalar

| Dosya | Değişiklik |
|-------|------------|
| `events/bus.py` | Events class'a yeni event'ler ekle |
| `core/plugins/loader.py` | Manifest validation ekle |
| `core/plugins/executor.py` | provides tracking, JobState kullanımı |
| `core/plugins/resolver.py` | after logic (provides-based) |

## 3.3 Satır Tahminleri

| Dosya | Mevcut | Ekleme | Toplam |
|-------|--------|--------|--------|
| `core/constants.py` | 0 | ~50 | ~50 |
| `state/models.py` | 0 | ~80 | ~80 |
| `events/bus.py` | 286 | ~20 | ~306 |
| `core/plugins/loader.py` | ~150 | ~40 | ~190 |
| `core/plugins/executor.py` | 414 | ~30 | ~444 |
| `core/plugins/resolver.py` | ~100 | ~50 | ~150 |

**Toplam yeni kod: ~270 satır**

---

# 4. KARARLAR

## 4.1 Kabul Edilenler

| Karar | Gerekçe |
|-------|---------|
| Trust-based plugin system | Endüstri standardı (VSCode, FlexGet, HA) |
| Standart provides listesi | Kaos önleme, validation |
| Sistem event'leri | Plugin custom event emit etmez |
| 4 stage sistemi | input/parse/metadata/output |

## 4.2 Reddedilenler

| Karar | Gerekçe |
|-------|---------|
| trusted_plugins config | Python'da enforce edilemez |
| FilesystemService wrapper | Endüstri standardı değil |
| HttpService wrapper | Endüstri standardı değil |
| Network monitoring | OS-level gerekir |
| File watching | Gereksiz complexity |
| Plugin custom events | Kaos yaratır |

---

# 5. EXECUTION PLAN

```
1. core/constants.py oluştur (Provides, Events)
2. state/models.py oluştur (JobState vb.)
3. events/bus.py güncelle (yeni event'ler)
4. core/plugins/loader.py güncelle (validation)
5. core/plugins/executor.py güncelle (provides tracking)
6. core/plugins/resolver.py güncelle (after logic)
7. Test yaz
```

---

# 6. REFERANS

Araştırılan projeler: Deno, Chrome Extensions, Node.js, Jenkins, Grafana, VSCode, FlexGet, Home Assistant, Obsidian, Sublime Text, Neovim, Pluggy/pytest, Domoticz

Sonuç: Python CLI uygulamalarında trust-based plugin sistemi endüstri standardı.

---

**Status: READY FOR EXECUTION**
