# 🎯 LOG SYSTEM - INDUSTRY STANDARD

## ✅ ŞİMDİ NASIL ÇALIŞIYOR

### Log Levels (Python Standard)

```python
DEBUG    = 10  # Her şey (verbose)
INFO     = 20  # Normal işlemler
WARNING  = 30  # Uyarılar
ERROR    = 40  # Hatalar
CRITICAL = 50  # Fatal hatalar
```

### Config Kullanımı

**config.yml:**

```yaml
options:
  log_level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Davranış

#### log_level: DEBUG

```
✅ DEBUG messages
✅ INFO messages
✅ WARNING messages
✅ ERROR messages
✅ CRITICAL messages
```

#### log_level: INFO (Default - Önerilen)

```
❌ DEBUG messages (gizli)
✅ INFO messages
✅ WARNING messages
✅ ERROR messages
✅ CRITICAL messages
```

#### log_level: WARNING

```
❌ DEBUG messages (gizli)
❌ INFO messages (gizli)
✅ WARNING messages
✅ ERROR messages
✅ CRITICAL messages
```

#### log_level: ERROR

```
❌ DEBUG messages (gizli)
❌ INFO messages (gizli)
❌ WARNING messages (gizli)
✅ ERROR messages
✅ CRITICAL messages
```

---

## 📝 CONSOLE OUTPUT KURALLARI

### 1. Pluginler

**Her zaman konsola yazar** (log level'dan bağımsız):

```python
class MyPlugin(OutputPlugin):
    def execute(self, job, services):
        self.info("Processing file", path=job.input.value)
        # ✅ Konsola gider (plugin log)
```

### 2. Debug Sistemi

**Log level threshold'a göre yazar**:

```python
debugger.debug("system", "Starting")  # Sadece DEBUG level'de
debugger.info("system", "Running")    # INFO ve üstü
debugger.warning("system", "Warning") # WARNING ve üstü
debugger.error("system", "Error")     # ERROR ve üstü
```

### 3. Başka Kimse Yazamaz!

❌ Core kod direkt `print()` kullanamaz  
❌ Services direkt console'a yazamaz  
✅ Sadece pluginler + debug sistemi

---

## 🚀 KULLANIM ÖRNEKLERİ

### Development (Her şeyi gör)

```yaml
options:
  log_level: DEBUG
```

```
2025-12-09T23:45:12+03:00  DEBUG  system    Starting scan
2025-12-09T23:45:12+03:00  DEBUG  registry  Loading plugins count=7
2025-12-09T23:45:12+03:00  INFO   scanner   Scanning target path=/movies
2025-12-09T23:45:12+03:00  INFO   scanner   Found file path=Matrix.mkv size_mb=1500
2025-12-09T23:45:13+03:00  INFO   renamer   Parsing filename=Matrix
2025-12-09T23:45:13+03:00  INFO   tmdb      Searching TMDb for movie name=The Matrix
```

### Production (Sadece önemli)

```yaml
options:
  log_level: INFO
```

```
2025-12-09T23:45:12+03:00  INFO   scanner   Scanning target path=/movies
2025-12-09T23:45:12+03:00  INFO   scanner   Found file path=Matrix.mkv size_mb=1500
2025-12-09T23:45:13+03:00  INFO   renamer   Parsing filename=Matrix
2025-12-09T23:45:13+03:00  INFO   tmdb      Searching TMDb for movie name=The Matrix
```

### Silent (Sadece hatalar)

```yaml
options:
  log_level: ERROR
```

```
# Sadece hata olursa bir şey gösterir
2025-12-09T23:45:15+03:00  ERROR  tmdb      API request failed error=Timeout
```

---

## 🎨 LOG FORMAT

### Standart Format

```
TIMESTAMP                  LEVEL  COMPONENT           [CONTEXT] MESSAGE
2025-12-09T23:45:12+03:00  INFO   scanner             Scanning target path=/movies
```

### Context İle

```
2025-12-09T23:45:12+03:00  INFO   scanner             [path=/movies recursive=true] Scanning target
```

---

## 💡 EN İYİ PRATİKLER

### Plugin Geliştiricileri İçin

```python
class MyPlugin(OutputPlugin):
    def execute(self, job, services):
        # Her adımda log
        self.info("Starting process", job_id=job.id)

        # Hata durumları
        if error:
            self.error("Process failed", error=str(error))
            return PluginResult.error_result(str(error))

        # Başarı
        self.info("Process complete", items_processed=count)
        return PluginResult.success_result(data=result)
```

### Production Önerisi

```yaml
options:
  log_level: INFO # ✅ Bu ideal!
```

**Neden INFO?**

- DEBUG çok verbose (her detay)
- INFO yeterli bilgi verir
- WARNING/ERROR önemli sorunları yakalar
- Performance iyi

### Debug İçin

```yaml
options:
  log_level: DEBUG # Geliştirme sırasında
```

---

## ✅ ÖZET

1. **Log Levels:** DEBUG < INFO < WARNING < ERROR < CRITICAL
2. **Default:** INFO (önerilen)
3. **Pluginler:** Her zaman yazar
4. **Debug Sistemi:** Level threshold'a göre
5. **Başkaları:** Yazamaz!

**Sistem artık industry standard!** 🚀
