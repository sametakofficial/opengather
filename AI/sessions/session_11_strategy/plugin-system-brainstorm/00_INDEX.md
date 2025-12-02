# PLUGIN SYSTEM BRAINSTORM - INDEX

```yaml
tarih: 2025-12-02
durum: final-review
hedef: 01-10 strategy dosyalarina override
```

---

## DOSYA YAPISI

```
plugin-system-brainstorm/
|-- 00_INDEX.md              # Bu dosya
|-- 01_MANIFEST_SCHEMA.md    # Plugin manifest yapisi
|-- 02_PROVIDES_SYSTEM.md    # Islem bazli provides
|-- 03_STAGE_EXECUTION.md    # 4 stage sistemi
|-- 04_PLUGIN_SERVICES.md    # Tek interface
|-- 05_CONFIG_SYSTEM.md      # FlexGet style config
|-- 06_STATE_MODEL.md        # JobState, RunState
|-- 07_ALIAS_SYSTEM.md       # Template alias
|-- 08_IMPLEMENTATION.md     # Execution plan
|-- 09_REQUIRES_SYSTEM.md    # UNIFIED requires + trigger_rule
|-- 10_STANDARD_TERMS.md     # Provides/Requires standart terimleri
```

---

## ENDUSTRI REFERANSLARI

| Proje | Pattern | Kaynak |
|-------|---------|--------|
| FlexGet | Task phases, YAML config | flexget.com |
| Home Assistant | Integration architecture, async | developers.home-assistant.io |
| pluggy/pytest | Hook-based, HookspecMarker | pluggy.readthedocs.io |
| Airflow | DAG, upstream/downstream | airflow.apache.org |
| Docker Compose | depends_on | docs.docker.com |
| OSGi | Provide-Capability, Require-Capability | osgi.org |

---

## KRITIK KARARLAR

```
1. provides = ISLEM BAZLI (http.response, fs.write)
   Kategori bazli DEGIL (metadata.movie REDDEDILDI)

2. stage = 4 DEGER (input, extract, enrich, output)
   6 stage REDDEDILDI (modify, finalize gereksiz)
   Isim degisiklikleri: parse->extract, metadata->enrich

3. requires = UNIFIED (TEK ALAN)
   after, waits_for, depends_on, triggers_on REDDEDILDI
   Hepsi requires icinde: job.* | provides.* | events.*

4. DEFAULT ALIAS SISTEMI
   Sistem inject: job, jobs, run, provides, events, config
   Kullanici: aliases: {m: job.plugins.tmdb.movie}

5. PluginServices = TEK INTERFACE
   get_debugger() global erisim KALDIRILACAK

6. FlexGet style config
   plugins: wrapper YOK, direkt plugin adi = key

7. HARDCODED YASAK
   requires: [renamer] YANLIS
   requires: [provides.data.parsed] DOGRU
```

---

## SESSION_11_STRATEGY OVERRIDE PLANI

```
01_state_structure_and_naming.md    <-- 06_STATE_MODEL.md
02_plugin_system_and_services.md    <-- 01, 02, 03, 04
03_orchestrator_and_execution_flow  <-- 03_STAGE_EXECUTION.md
04_config_manifest_and_external     <-- 05_CONFIG_SYSTEM.md
10_final_decisions.md               <-- TUM DOSYALAR
```

---

## ARASTIRMA SONUCLARI

### FlexGet
- 5 phase: input, filter, output, metadata, modification
- YAML config, no plugins: wrapper
- Trust-based plugin system

### Home Assistant
- Integration = component + platforms
- hass object = merkezi interface
- async_setup pattern

### pluggy
- HookspecMarker: hook tanimla
- HookimplMarker: hook implement et
- PluginManager: registry ve caller

### Sonuc
Python CLI uygulamalarinda trust-based, manifest-declared plugin sistemi endustri standardi.

---

## CHANGELOG

```
2025-12-02: Ilk versiyon
- Manifest schema tamamlandi
- Provides degerleri belirlendi (islem bazli)
- PluginServices interface tasarlandi
- Config merge logic tanimlandii
```
