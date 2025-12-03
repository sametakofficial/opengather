# PLUGIN BRAINSTORM V2 - INDEX

```yaml
tarih: 2025-12-03
durum: aktif
odak: Conflict Detection, Provide Lock, Config/Manifest Iliskisi
```

---

## DOSYALAR

```
plugin-brainstorm-v2/
|-- 00_INDEX.md                      # Bu dosya
|-- 01_CONFLICT_DETECTION.md         # Provides conflict tespiti
|-- 02_PROVIDE_LOCK_SYSTEM.md        # fs.write:/path, job.update lock
|-- 03_CONFIG_MANIFEST_RELATION.md   # Config/Manifest import ve override
|-- 04_VALIDATION_PHASES.md          # Startup vs Runtime validation
|-- 05_CRITICAL_ANALYSIS.md          # Seytanin avukatligi, elestiri
|-- 06_INPUT_OUTPUT_STRUCTURE.md     # input.value/data, output.values/data
```

---

## OZET

Bu brainstorm session_11_strategy uzerine insa edilmistir. Temel konular:

1. **Conflict Detection**: Ayni stage'de paralel calisan pluginlerin cakisma tespiti
2. **Provide Lock**: Path-based kilitleme (fs.write:/data/archive)
3. **Config/Manifest**: Import sistemi, override kurallari
4. **Validation**: Static vs dynamic, startup hatasi vs runtime uyari
5. **Input/Output Structure**: input.value/data, output.values/data, virtual dosya destegi

---

## ILISKILI DOSYALAR

- `../10_STANDARD_TERMS.md`: Mevcut provides listesi
- `../02_plugin_system_and_services.md`: Plugin sistemi
- `../04_config_manifest_and_external_tasks.md`: Config sistemi
- `../../PHILOSOPHY.md`: Temel felsefeler (GUNCELLENDI)

---

## KARARLAR OZETI

```
+----------------------------------------------------------+
|              FINAL KARARLAR                               |
+----------------------------------------------------------+
|                                                           |
|  FS LOCK: EVET                                            |
|  - Syntax: fs.write:/path                                |
|  - {{config.*}} gecerli, {{job.*}} gecersiz              |
|  - Static prefix cikarma                                 |
|  - Tasker icin manual provides                           |
|                                                           |
|  JOB LOCK: HAYIR                                          |
|  - Namespace izolasyonu yeterli                          |
|  - requires ile siralama cozum                           |
|  - Cross-namespace yazim = anti-pattern                  |
|                                                           |
|  CONFIG/MANIFEST:                                         |
|  - Import (tek merged state)                             |
|  - Uste import = config kazanir                          |
|  - Immutable: name, version, stage, class_name           |
|  - List merge = replace                                  |
|                                                           |
|  VALIDATION:                                              |
|  - Startup: conflict detection, dynamic var check        |
|  - Pre-execution: requires satisfaction                  |
|  - Runtime: template, file ops (run durmasin)            |
|                                                           |
|  INPUT/OUTPUT:                                            |
|  - input.path -> input.value (virtual destegi)           |
|  - input.data: Input plugin ek datasi                    |
|  - output.values: Cikti path/deger listesi               |
|  - output.data: Task sonuclari (raw)                     |
|  - Her plugin data'yi plugins.X'e de yazar               |
|                                                           |
|  PHASE KURALLARI:                                         |
|  - input: Job olustur, value+data doldur                 |
|  - parse/data: Analiz, dosya KAYDETME (cache haric)      |
|  - output: Cikti olustur, values+data doldur             |
|                                                           |
+----------------------------------------------------------+
```

---

## PHILOSOPHY.MD GUNCELLEMELER

Asagidaki bolumler eklendi:

- 11.4 Dinamik Degisken Yasagi
- 11.5 Job Lock Gereksizligi
- 12. VALIDATION PRENSIPLERI
- 13. INPUT/OUTPUT YAPISI (path->value, data, values)

---

**Son Guncelleme:** 2025-12-03
