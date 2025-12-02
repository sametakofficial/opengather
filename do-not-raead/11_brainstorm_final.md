# BRAINSTORM: PLUGIN ARCHITECTURE FINAL

```yaml
date: 2025-12-01
status: decision-ready
```

---

## 1. DEPENDENCY SİSTEMİ

### 1.1 Dört Manifest Değeri

| Değer | Anlam | Örnek |
|-------|-------|-------|
| `requires` | Bu data olmadan başlama | `requires: [renamer.parsed]` |
| `provides` | Bu capability'leri sağlarım | `provides: [metadata.movie, api.call]` |
| `waits_for` | Bu provides'ları veren plugin'ler bitsin | `waits_for: [api.call]` |
| `triggers_on` | Bu event'lerde tekrar çalış (per_job only) | `triggers_on: [file.created]` |

### 1.2 Farklar

```
requires vs waits_for:
- requires = data path (renamer.parsed.movie)
- waits_for = capability (api.call)

triggers_on vs waits_for:
- triggers_on = her event'te tekrar çalış
- waits_for = sadece bir kez, plugin'ler bitince
```

---

## 2. STAGE SİSTEMİ

### 2.1 Felsefe

```
Bağlılık EVENT ise → Stage gereksiz
  Örnek: file.created dinleyen plugin, triggers_on kullanır

Bağlılık KATEGORİ ise → Stage gerekli
  Örnek: Metadata plugin'leri hangi event ile tespit edilir?
         Edilemez. Stage ile gruplandırılır.
```

### 2.2 Stage Listesi

| Stage | Amaç | Örnekler |
|-------|------|----------|
| `input` | Job oluşturma | scanner, file-reader |
| `parse` | Input parse | renamer |
| `metadata` | Data zenginleştirme | tmdb, tvdb, ffprobe |
| `process` | İşleme, modifikasyon | tasker, duplicate-cleaner, ai-detector |
| `sync` | Senkronizasyon | rclone, notification |

### 2.3 Stage + per_run

```
per_run plugin'ler stage sıralamasına uyar.
Stage İÇİNDE sıralama = waits_for ile.

Örnek:
- Rclone (sync stage, per_run)
- waits_for: [file.write] → Tasker bitsin
```

---

## 3. EXTERNAL CONFIG (Import Sistemi)

### 3.1 Home Assistant Pattern

```yaml
# Home Assistant
automation: !include automation.yaml
sensor: !include_dir_list sensors/
```

### 3.2 Archiverr Önerisi

```yaml
# config.yml
scanner:
  !include: ./scanner-config.yml

tasker:
  tasks:
    !include_list: ./tasks/
```

### 3.3 Import Türleri

| Syntax | Anlam |
|--------|-------|
| `!include file.yml` | Tek dosya import |
| `!include_list dir/` | Dizini list olarak import |
| `!include_merge dir/` | Dizini merge ederek import |

---

## 4. PROVIDES DISCOVERY

### 4.1 Problem

Plugin'in dış dünya ile iletişimi (API, dosya) nasıl tespit edilir?

### 4.2 Çözüm: Deklaratif + Trust

```yaml
# manifest.yml
provides:
  - api.call      # API çağrısı yapıyorum
  - file.write    # Dosya yazıyorum
  - file.delete   # Dosya siliyorum
```

**Neden otomatik tespit yok?**
- Stremio: Plugin kendi sunucusunda, kontrol yok
- FlexGet: Trust-based, manifest ile declare
- OSGi: Provide-Capability manifest'te

**Sonuç:** Otomatik tespit maliyet/fayda düşük. Manifest deklarasyonu yeterli.

### 4.3 Standart Provides Değerleri

```
Dosya İşlemleri:
- file.read
- file.write
- file.delete
- file.move

API İşlemleri:
- api.call

Metadata:
- metadata.movie
- metadata.show
- metadata.file

Output:
- output.print
- output.save
```

---

## 5. TASKER

### 5.1 Tasker = Plugin

```yaml
# config.yml
tasker:
  tasks:
    - name: print_movie
      type: print
      template: "{{ job.plugins.tmdb.movie.title }}"
```

### 5.2 Manifest

```yaml
# plugins/tasker/manifest.yml
name: tasker
stage: process
mode: per_job
provides:
  - file.write      # save yaparsa
  - output.print
  - output.save
```

### 5.3 Diğer Plugin'ler de Yapabilir

services.filesystem ile her plugin print/save yapabilir.
Tasker = configurable, user-friendly wrapper.

---

## 6. FLEXGET-STYLE CONFIG

### 6.1 Mevcut

```yaml
plugins:
  scanner:
    enabled: true
    targets: [/downloads]
  tmdb:
    api_key: xxx
```

### 6.2 Önerilen

```yaml
# plugins: parent yok
scanner:
  targets: [/downloads]

tmdb:
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    !include_list: ./tasks/
```

### 6.3 Enabled/Disabled

```yaml
# Plugin disable etmek için
tmdb: false

# veya
tmdb:
  enabled: false
  api_key: xxx
```

---

## 7. MANIFEST SCHEMA (Final)

```yaml
name: string
version: string
description: string
stage: input | parse | metadata | process | sync
mode: per_job | per_run

# Dependency
requires: [data.paths]           # Data requirement
provides: [capabilities]         # What I provide
waits_for: [capabilities]        # Wait for these providers
triggers_on: [events]            # Re-run on events (per_job only)

# Implementation
class_name: string
entry_point: string              # Default: client.py

# Config
config_schema:
  field:
    type: string | int | bool | list | dict
    required: bool
    default: any
```

---

## 8. EXECUTION FLOW

```
1. Config load
   └── !include resolve
   └── ${ENV_VAR} resolve

2. Plugin discovery
   └── Manifest load
   └── Topological sort (requires/waits_for)

3. Stage execution (sırayla)
   ├── input stage
   │   └── Scanner (per_run) → jobs oluştur
   ├── parse stage
   │   └── Renamer (per_job) → parse
   ├── metadata stage
   │   └── TMDb (per_job) → metadata
   ├── process stage
   │   └── Tasker (per_job) → print/save
   │   └── DuplicateCleaner (per_run, waits_for: [output.save])
   └── sync stage
       └── Rclone (per_run, waits_for: [file.write])
```

---

## 9. KARARLAR

| Konu | Karar |
|------|-------|
| Dependency değerleri | requires, provides, waits_for, triggers_on |
| Stage sayısı | 5: input, parse, metadata, process, sync |
| External config | !include, !include_list, !include_merge |
| Provides discovery | Manifest deklarasyonu (trust-based) |
| Tasker | Plugin, process stage'de |
| Config style | FlexGet (no plugins: parent) |

---

## 10. GÜNCELLENECEK DOSYALAR

```
02_plugin_system_and_services.md → Yeni manifest schema
03_orchestrator_and_execution_flow.md → Stage execution
04_config_manifest_and_external_tasks.md → External config, FlexGet style
10_final_decisions.md → Yeni kararlar
PHILOSOPHY.md → ✅ Oluşturuldu
```

---

**Status: DECISION-READY**
