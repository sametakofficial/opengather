# SESSION 16 - PLUGIN COMMUNICATION REFACTOR STRATEGY

## OZET

Plugin iletisim sistemi yeniden tasarlaniyor. Ana degisiklikler:
- Plugin status job/run icine tasiniyor
- Plugin data flat list yapisina geciliyor
- Plugin-agnostic iletisim API

---

## 1. PLUGINS STATE YAPISI

### ONCEKI YAKLASIM (REDDEDILDI)

```python
plugins: {
  "run": {
    "scanner": {...}
  },
  "job": {
    "tmdb": {...},
    "renamer": {...}
  }
}
```

Problem: Gereksiz gruplama. Tek bir run objesi icin ayri kategori mantikli degil.

### YENI YAKLASIM (KABUL EDILDI)

Flat list, her obje kendi tipini belirtir:

```python
plugins: [
  {
    "job_id": "job_abc123_0",
    "renamer": {"parsed": {...}},
    "tmdb": {"movie": {...}, "show": {...}},
    "tasker": {"tasks": {...}}
  },
  {
    "job_id": "job_abc123_1",
    "renamer": {"parsed": {...}},
    "tmdb": {"movie": {...}}
  },
  {
    "run_id": "run_abc123",
    "scanner": {"count": 10, "targets": [...]}
  }
]
```

Avantajlar:
- Tek seviye, flat structure
- job_id varsa job, run_id varsa run
- type alani gereksiz (ID'den belli)
- Tum objeler ayni seviyede, gruplama yok

### ALTERNATIF: DICT FORMATINDA

```python
plugins: {
  "job_abc123_0": {
    "renamer": {"parsed": {...}},
    "tmdb": {"movie": {...}}
  },
  "job_abc123_1": {
    "renamer": {"parsed": {...}},
    "tmdb": {"movie": {...}}
  },
  "run_abc123": {
    "scanner": {"count": 10}
  }
}
```

Key olarak ID kullanilir. job_ prefix ile baslayan job, run_ prefix ile baslayan run.

---

## 2. PLUGIN STATUS YAPISI

Status artik plugin data icinde degil, job/run status icinde:

```python
job: {
  "id": "job_abc123_0",
  "status": {
    "state": "completed",
    "plugins": {
      "renamer": {
        "state": "completed",
        "success": true,
        "started_at": "2024-12-16T10:00:00Z",
        "finished_at": "2024-12-16T10:00:01Z",
        "duration_ms": 1000
      },
      "tmdb": {
        "state": "completed",
        "success": true,
        "started_at": "2024-12-16T10:00:01Z",
        "finished_at": "2024-12-16T10:00:02Z",
        "duration_ms": 800
      }
    }
  }
}

run: {
  "id": "run_abc123",
  "status": {
    "plugins": {
      "scanner": {
        "state": "completed",
        "success": true,
        "started_at": "2024-12-16T09:59:59Z",
        "finished_at": "2024-12-16T10:00:00Z",
        "duration_ms": 1200
      }
    }
  }
}
```

Mantik:
- Status sistem tarafindan yonetilir
- Plugin data plugin tarafindan yonetilir
- Ayrim net ve temiz

---

## 3. PLUGIN ILETISIM API

### ISIMLENDIRME

Tum metodlar snake_case:

```python
create_job()      # camelCase degil
update_job()
update_plugin()
get_plugin_data()
```

### METOD IMZALARI

```python
class PluginServices:
    
    def create_job(self, input_value: str, input_data: dict) -> str:
        """
        Yeni job olustur.
        
        Returns:
            job_id
        """
    
    def update_job(self, job_id: str, path: str, value: Any) -> None:
        """
        Job state guncelle.
        
        Args:
            job_id: Hedef job
            path: Dot notation (ornek: "output.data.tasks")
            value: Deger
        """
    
    def update_plugin(
        self,
        target_id: str,      # job_id veya run_id
        plugin_name: str,
        data: dict
    ) -> None:
        """
        Plugin data guncelle.
        
        Args:
            target_id: job_abc123_0 veya run_abc123
            plugin_name: tmdb, renamer, scanner vs
            data: Plugin datasi
        
        Ornekler:
            update_plugin("job_abc123_0", "tmdb", {"movie": {...}})
            update_plugin("run_abc123", "scanner", {"count": 10})
        """
    
    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict:
        """
        Plugin datasini al.
        """
```

### ID ZORUNLULUGU

Her iletisimde ID belirtmek zorunlu:

```python
# YANLIS - ID yok
services.update_plugin({"movie": data})

# DOGRU - ID var
services.update_plugin("job_abc123_0", "tmdb", {"movie": data})
```

Bu zorunluluk sayesinde:
- Her plugin her metodu kullanabilir (plugin-agnostic)
- Per run plugin job'a veri ekleyebilir
- Per job plugin run'a veri ekleyebilir
- Tam esneklik

---

## 4. PLUGIN STATUS TRACKING

Sistem tarafindan otomatik yonetilir:

```python
# Sistem cagiriyor, plugin degil
def mark_plugin_started(target_id: str, plugin_name: str) -> None:
    """
    Plugin basladiginda sistem tarafindan cagrilir.
    
    Islemler:
        - job/run.status.plugins.{name}.started_at = now()
        - job/run.status.plugins.{name}.state = "running"
    """

def mark_plugin_completed(
    target_id: str,
    plugin_name: str,
    success: bool,
    error: str = None
) -> None:
    """
    Plugin bittiginde sistem tarafindan cagrilir.
    
    Islemler:
        - finished_at = now()
        - duration_ms = finished_at - started_at
        - state = "completed" veya "failed"
        - success = True/False
        - error = hata mesaji (varsa)
    """
```

---

## 5. NIHAI STATE YAPISI

```python
{
  "run": {
    "id": "run_abc123",
    "status": {
      "state": "running",
      "plugins": {
        "scanner": {"state": "completed", "success": true, ...}
      }
    }
  },
  
  "job": {
    "id": "job_abc123_0",
    "input": {"value": "/path/to/file.mkv", "data": {...}},
    "output": {"values": [...], "data": {...}},
    "status": {
      "state": "running",
      "plugins": {
        "renamer": {"state": "completed", "success": true, ...},
        "tmdb": {"state": "completed", "success": true, ...},
        "tasker": {"state": "running", ...}
      }
    }
  },
  
  "jobs": [
    {"id": "job_abc123_0", ...},
    {"id": "job_abc123_1", ...}
  ],
  
  "plugins": {
    "job_abc123_0": {
      "renamer": {"parsed": {...}},
      "tmdb": {"movie": {...}, "show": {...}},
      "tasker": {"tasks": {...}}
    },
    "job_abc123_1": {
      "renamer": {"parsed": {...}},
      "tmdb": {"movie": {...}}
    },
    "run_abc123": {
      "scanner": {"count": 10, "targets": [...]}
    }
  }
}
```

---

## 6. SERVIS SORUMLULUKLARI

PluginServices su isleri halleder:

1. ID generation (UUID format)
2. Event bus notifications (plugin.updated, job.created)
3. Timestamp management (started_at, finished_at, duration_ms)
4. Dual state update (job + jobs sync)
5. Validation (job/plugin var mi)

Plugin direkt state'e erismez, servis kullanir.

---

## 7. MIGRASYON ADIMLARI

### Adim 1: Yeni servis metodlari

```python
# Yeni metodlar eklenir
create_job()
update_job()
update_plugin()
get_plugin_data()

# Eski metodlar deprecated
updatePlugin()  # -> update_plugin()
updateJob()     # -> update_job()
createJob()     # -> create_job()
```

### Adim 2: Plugin status tasima

```python
# Onceki
plugins.tmdb.status = {...}

# Sonra
job.status.plugins.tmdb = {...}
```

### Adim 3: Plugins yapisini degistir

```python
# Onceki
plugins.tmdb.data = {...}

# Sonra
plugins["job_abc123_0"].tmdb = {...}
```

### Adim 4: Tum pluginleri guncelle

Her plugin yeni API kullanacak sekilde guncellenir.

---

## 8. KARAR OZETI

| Konu | Karar |
|------|-------|
| Plugins yapisi | Flat dict, key = target_id |
| Plugin status | job/run.status.plugins icinde |
| Plugin data | plugins[target_id][plugin_name] icinde |
| ID zorunlulugu | Her iletisimde target_id zorunlu |
| Isimlendirme | snake_case |
| Tracking | Sistem yonetir, plugin dokunmaz |
