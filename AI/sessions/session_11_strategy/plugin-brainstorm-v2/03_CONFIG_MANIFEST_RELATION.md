# CONFIG VE MANIFEST ILISKISI

```yaml
tarih: 2025-12-03
durum: brainstorm
odak: Import mekanizmasi, override kurallari, merge stratejisi
```

---

## 1. TEMEL FELSEFE

```
+----------------------------------------------------------+
|              CONFIG/MANIFEST ILISKISI                     |
+----------------------------------------------------------+
|                                                           |
|  config.yml  = KULLANICI TANIMI (override eder)          |
|  manifest.yml = PLUGIN DEFAULT (base degerler)           |
|                                                           |
|  ILKE: config.yml HER ZAMAN KAZANIR                      |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. IMPORT MEKANIZMASI

### 2.1 Kavramsal Model

```
config.yml (kullanici)          manifest.yml (plugin)
     |                               |
     |     Plugin Discovery          |
     |<------------------------------|
     |                               |
     v                               v
+----------------------------------------------------------+
|                    MERGE ENGINE                           |
|                                                           |
|  1. manifest.yml oku (base)                              |
|  2. config.yml plugin wrapper'ina import et              |
|  3. Ayni key = config kazanir                            |
|                                                           |
+----------------------------------------------------------+
     |
     v
Merged Config (Final)
```

### 2.2 Import Pozisyonu

```yaml
# Soru: manifest.yml nereye import edilir?
# Cevap: USTE (ilk satirlara)

# SONUC: config.yml'de ne yazildiysa O GECERLI
# Cunku alt satirlar ust satirlari override EDEMEZ
```

**Mantik:**

```yaml
# config.yml (kullanici yazdigi)
tmdb:
  api_key: USER_KEY
  language: tr-TR
# manifest.yml (plugin default)
# tmdb wrapper'inin USTUNE import edilir
```

**Merge sonrasi:**

```yaml
tmdb:
  # manifest.yml'den (uste import edildi)
  stage: data
  class_name: TMDbPlugin
  requires: [job.plugins.renamer.parsed]
  provides: [http.request, state.update]
  api_key: DEFAULT_KEY        # <-- manifest default
  language: en-US             # <-- manifest default

  # config.yml'den (altta, override eder)
  api_key: USER_KEY           # <-- KAZANAN
  language: tr-TR             # <-- KAZANAN
```

**FINAL DEGER:**

```yaml
tmdb:
  stage: data
  class_name: TMDbPlugin
  requires: [job.plugins.renamer.parsed]
  provides: [http.request, state.update]
  api_key: USER_KEY # config kazandi
  language: tr-TR # config kazandi
```

---

## 3. OVERRIDE KURALLARI

### 3.1 Kural: Alt Satir Kazanir

```
+----------------------------------------------------------+
|              MERGE KURALI                                 |
+----------------------------------------------------------+
|                                                           |
|  YAML'da ayni key iki kez yazilirsa:                     |
|  - SON YAZAN (alt satir) KAZANIR                         |
|                                                           |
|  ORNEK:                                                   |
|  key: value1                                             |
|  key: value2                                             |
|  SONUC: key = value2                                     |
|                                                           |
+----------------------------------------------------------+
```

### 3.2 Manifest USTE Import = Config Kazanir

```
manifest.yml USTE import edilir
     |
     v
+---------------------------+
|  manifest.yml degerleri   |  <- UST (once)
+---------------------------+
|  config.yml degerleri     |  <- ALT (sonra, KAZANIR)
+---------------------------+
```

### 3.3 Immutable Fields

```
+----------------------------------------------------------+
|              DEGISTIRILEMEZ ALANLAR                       |
+----------------------------------------------------------+
|                                                           |
|  IMMUTABLE (config override EDEMEZ):                     |
|  - name                                                   |
|  - version                                                |
|  - stage                                                  |
|  - class_name                                             |
|  - entry_point                                            |
|                                                           |
|  MUTABLE (config override EDEBILIR):                     |
|  - requires                                               |
|  - provides                                               |
|  - trigger_rule                                           |
|  - reactive                                               |
|  - config_schema icindeki degerler                        |
|  - Tum kullanici ayarlari (api_key, language, vb)        |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. ALTERNATI YAKLASIM: AYRI STATE

### 4.1 Import vs Ayri Tutma

```
+----------------------------------------------------------+
|  SECENEK A: Import (SECILEN)                              |
+----------------------------------------------------------+
|                                                           |
|  manifest.yml -> config.yml icine import                 |
|  Tek merged state                                        |
|  Override kurallari basit                                |
|                                                           |
|  AVANTAJ:                                                 |
|  - Tek config objesi                                     |
|  - Basit validation                                      |
|  - Tutarli erisim                                        |
|                                                           |
|  DEZAVANTAJ:                                              |
|  - Merge logic gerekli                                   |
|  - Immutable field kontrolu                              |
|                                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  SECENEK B: Ayri State                                    |
+----------------------------------------------------------+
|                                                           |
|  manifest.yml ayri state                                 |
|  config.yml ayri state                                   |
|  Runtime'da birlestir                                    |
|                                                           |
|  AVANTAJ:                                                 |
|  - Net ayrim                                             |
|  - Merge karmasikligi yok                                |
|                                                           |
|  DEZAVANTAJ:                                              |
|  - Iki farkli state yonet                                |
|  - "Hangi deger gecerli?" karisikligi                    |
|  - Override icin ayri logic                              |
|  - Template'de {{config.x}} vs {{manifest.x}} karmasasi  |
|                                                           |
+----------------------------------------------------------+
```

### 4.2 Endustri Karsilastirmasi

```
+----------------------------------------------------------+
|  FRAMEWORK         YAKLASIM                               |
+----------------------------------------------------------+
|                                                           |
|  FlexGet           Config tek, plugin schema inline      |
|  Home Assistant    Config tek, component schema merge    |
|  Ansible           Playbook + role vars merge            |
|  Terraform         Provider + resource merge             |
|                                                           |
|  SONUC: Import ve merge ENDUSTRI STANDARDI               |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. IMPLEMENTATION

### 5.1 Merge Algoritmasi

```python
def merge_manifest_into_config(
    config: Dict,
    plugin_name: str,
    manifest: Dict
) -> Dict:
    """Manifest'i config plugin wrapper'ina merge et"""

    IMMUTABLE = {'name', 'version', 'stage', 'class_name', 'entry_point'}

    plugin_config = config.get(plugin_name, {})

    # Manifest once (base)
    merged = {}
    for key, value in manifest.items():
        merged[key] = value

    # Config sonra (override)
    for key, value in plugin_config.items():
        if key in IMMUTABLE and key in merged:
            continue  # Immutable, skip
        merged[key] = value

    return merged
```

**Uyari:** Ornek kod, yaklasimi gosterir. Execution session'da mevcut codebase'e uyarlanmalidir.

### 5.2 Merge Flow

```
                    CONFIG LOAD
                         |
                         v
+----------------------------------------------------------+
|  1. config.yml oku                                       |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  2. Plugin discovery (manifest.yml'leri bul)             |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  3. Her plugin icin merge:                               |
|     merged[plugin] = merge(manifest, config[plugin])     |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  4. Merged config'i validate et                          |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  5. Conflict detection calistir                          |
+----------------------------------------------------------+
```

---

## 6. PROVIDES OVERRIDE

### 6.1 Manifest'te Provides

```yaml
# manifest.yml
provides:
  - http.request
  - state.update
```

### 6.2 Config'de Override

```yaml
# config.yml
tmdb:
  provides:
    - http.request
    - state.update
    - fs.write:/data/posters # EKLENDI
```

### 6.3 Merge Davranisi

```
+----------------------------------------------------------+
|  PROVIDES MERGE                                           |
+----------------------------------------------------------+
|                                                           |
|  SECENEK A: Replace (SECILEN)                            |
|  config.provides varsa, manifest.provides'i DEGISTIR     |
|                                                           |
|  SECENEK B: Extend                                        |
|  config.provides'i manifest.provides'a EKLE              |
|                                                           |
|  KARAR: Replace                                           |
|  - Kullanici tam kontrol ister                           |
|  - Extend karmasiklik yaratir                            |
|  - "Sadece fs.write ekle" icin tum listeyi yaz           |
|                                                           |
+----------------------------------------------------------+
```

---

## 7. FS.WRITE LOCK OVERRIDE

### 7.1 Senaryo

```yaml
# manifest.yml
provides:
  - fs.write:/data/archive # Plugin default

# config.yml
tasker:
  provides:
    - fs.write:/data # Kullanici daha genis lock
```

### 7.2 Sonuc

```yaml
# Merge sonrasi
provides:
  - fs.write:/data # Config kazandi
```

**Bu Dogru mu?**

```
+----------------------------------------------------------+
|              ANALIZ                                       |
+----------------------------------------------------------+
|                                                           |
|  manifest: fs.write:/data/archive (dar)                  |
|  config:   fs.write:/data (genis)                        |
|                                                           |
|  Kullanici daha genis kilitliyor.                        |
|  Potansiyel conflict artabilir.                          |
|  AMA: Kullanici bilerek yapti, sorumlulupu kabul etti.   |
|                                                           |
|  SONUC: Gecerli, uyari verilmez.                         |
|                                                           |
+----------------------------------------------------------+
```

---

## 8. PHILOSOPHY.MD EKLEME

Asagidaki felsefe PHILOSOPHY.md'ye eklenmelidir:

```
## CONFIG/MANIFEST ILISKISI

### Temel Prensip

config.yml  = KAYNAK (kullanici tanimli, override eder)
manifest.yml = DEFAULT (plugin tanimli, base degerler)

Merge: manifest USTE import, config ALT satirlarda = config KAZANIR

### Immutable Fields (Degistirilemez)

name, version, stage, class_name, entry_point

Bu alanlar manifest.yml'de tanimlanir, config.yml override EDEMEZ.

### Mutable Fields (Degistirilebilir)

requires, provides, trigger_rule, reactive, config_schema alanlari

Bu alanlar config.yml ile override edilebilir.

### Merge Kurallari

1. manifest.yml once okunur (base)
2. config.yml uzerine yazilir (override)
3. Ayni key = config kazanir
4. Nested dict = recursive merge
5. List = replace (extend degil)
```

---

## 9. SONUC

```
+----------------------------------------------------------+
|              FINAL KARARLAR                               |
+----------------------------------------------------------+
|                                                           |
|  IMPORT:                                                  |
|  - manifest.yml USTE import edilir                       |
|  - config.yml ALT satirlarda kalir                       |
|  - Alt satirlar kazanir = config override eder           |
|                                                           |
|  IMMUTABLE:                                               |
|  - name, version, stage, class_name, entry_point        |
|                                                           |
|  LIST MERGE:                                              |
|  - Replace (extend degil)                                |
|  - requires, provides = config'deki gecerli              |
|                                                           |
|  AYRI STATE:                                              |
|  - HAYIR, tek merged state                               |
|  - Endustri standardi ile uyumlu                         |
|                                                           |
+----------------------------------------------------------+
```

---

**Son Guncelleme:** 2025-12-03
