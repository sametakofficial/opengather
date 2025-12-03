# INPUT/OUTPUT STRUCTURE

```yaml
tarih: 2025-12-03
durum: brainstorm
odak: input.value, input.data, output.values, output.data yapisi
```

---

## 1. PATH YERINE VALUE - VIRTUAL DOSYA DESTEGI

### 1.1 Problem

```
+----------------------------------------------------------+
|              MEVCUT YAKLASIM                              |
+----------------------------------------------------------+
|                                                           |
|  input.path = /data/movies/movie.mkv                     |
|                                                           |
|  SORUN:                                                   |
|  - Sadece fiziksel dosya yollarini destekler             |
|  - Virtual dosyalar icin yetersiz                        |
|  - "Su filmi arat, metadatasini bul" gibi use case'ler   |
|    desteklenmez                                           |
|                                                           |
+----------------------------------------------------------+
```

### 1.2 Cozum: input.value

```
+----------------------------------------------------------+
|              YENI YAKLASIM                                |
+----------------------------------------------------------+
|                                                           |
|  input.value = Fiziksel VEYA virtual girdi               |
|                                                           |
|  ORNEKLER:                                                |
|  - Fiziksel: /data/movies/movie.mkv                      |
|  - Virtual:  "The Matrix 1999"                           |
|  - Virtual:  tmdb://movie/603                            |
|  - Virtual:  imdb://tt0133093                            |
|                                                           |
+----------------------------------------------------------+
```

### 1.3 Endustri Karsilastirmasi

```
+----------------------------------------------------------+
|  FRAMEWORK         YAKLASIM                               |
+----------------------------------------------------------+
|                                                           |
|  Radarr/Sonarr     Movie/Show object (virtual entity)    |
|  Plex              Media item (virtual + physical)       |
|  Jellyfin          Item (library agnostic)               |
|  FlexGet           Entry (generic, URL/path/virtual)     |
|                                                           |
|  SONUC: Virtual + Physical ENDUSTRI STANDARDI            |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. JOB STRUCTURE

### 2.1 Yeni Job Yapisi

```yaml
job:
  # System fields
  index: 0
  id: "uuid-xxx"
  status: completed

  # INPUT SECTION
  input:
    value: "/data/movies/movie.mkv" # Eski: path
    data: # Input plugin'in ek datasi
      filename: "movie.mkv"
      extension: "mkv"

  # OUTPUT SECTION
  output:
    values: # Coklu ciktilar (eski: paths)
      - "/srv/archive/Movie (2024)/Movie.mkv"
      - "/srv/archive/Movie (2024)/Movie.nfo"
    data: # Output plugin'in datasi
      tasks: # Dict, array degil
        save_movie:
          type: save
          template: "..."
          output: "/srv/archive/Movie (2024)/Movie.mkv"
        log_movie:
          type: print
          template: "..."
          output: "movie name : Movie | year: 2024 | metadata : found"

  # PLUGIN DATA
  plugins:
    scanner:
      filename: "movie.mkv"
      extension: "mkv"
    renamer:
      parsed:
        title: "Movie"
        year: 2024
    tmdb:
      status:
        success: true
      movie:
        id: 12345
        title: "Movie"
        year: 2024
    tasker:
      tasks:
        - name: save_movie
          type: save
          success: true
```

---

## 3. INPUT PLUGIN DAVRANISI

### 3.1 Input Plugin Ne Yapar?

```
+----------------------------------------------------------+
|              INPUT PLUGIN SORUMLULUKLARI                  |
+----------------------------------------------------------+
|                                                           |
|  1. Job olustur                                          |
|  2. job.input.value doldur (fiziksel veya virtual)       |
|  3. job.input.data doldur (plugin'in ek datasi)          |
|  4. job.plugins.{plugin_name} doldur (ayni data)         |
|                                                           |
+----------------------------------------------------------+
```

### 3.2 Neden input.data VE plugins.X Ayni?

```
+----------------------------------------------------------+
|              AYRI TUTMA SEBEBI                            |
+----------------------------------------------------------+
|                                                           |
|  SORU: Neden ayni datayi iki yere yaziyoruz?             |
|                                                           |
|  CEVAP:                                                   |
|  - input.data = Sistem tarafindan KNOWN lokasyon         |
|  - plugins.X = Plugin-specific lokasyon                  |
|                                                           |
|  AVANTAJ:                                                 |
|  - Hangi input plugin job olusturdu bilmeye GEREK YOK    |
|  - input.data HER ZAMAN input plugin datasi              |
|  - Otomatik mapping gereksiz                             |
|  - Query kolayligi: job.input.data.filename              |
|                                                           |
+----------------------------------------------------------+
```

### 3.3 Input Plugin Ornek

```python
class ScannerPlugin:
    """Input plugin ornegi"""

    def execute(self, services: PluginServices) -> PluginResult:
        # 1. Dosyalari tara
        files = self._scan_directory(self.config.path)

        results = []
        for file_path in files:
            # 2. Data hazirla
            data = {
                'filename': file_path.name,
                'extension': file_path.suffix.lstrip('.')
            }

            # 3. Job olustur
            job = services.state.create_job(
                input_value=str(file_path),  # job.input.value
                input_data=data               # job.input.data
            )

            # 4. Plugin datasini kaydet (ayni data)
            services.state.update_plugin_data(
                job_id=job.id,
                plugin_name='scanner',
                data=data                      # job.plugins.scanner
            )

            results.append(job)

        return PluginResult(success=True, jobs=results)
```

---

## 4. OUTPUT PLUGIN DAVRANISI

### 4.1 Output Plugin Ne Yapar?

```
+----------------------------------------------------------+
|              OUTPUT PLUGIN SORUMLULUKLARI                 |
+----------------------------------------------------------+
|                                                           |
|  1. Task'lari calistir (save, print, etc.)               |
|  2. job.output.values doldur (cikti path'leri/degerleri) |
|  3. job.output.data doldur (task sonuclari)              |
|  4. job.plugins.{plugin_name} doldur (ayni data)         |
|                                                           |
+----------------------------------------------------------+
```

### 4.2 output.values vs output.data

```
+----------------------------------------------------------+
|              FARK                                         |
+----------------------------------------------------------+
|                                                           |
|  output.values:                                           |
|  - Cikti path'leri veya virtual sonuclar                 |
|  - Birden fazla olabilir (array)                         |
|  - Veritabani indexleme icin                             |
|  - "Bu job hangi dosyalari olsuturdu?" sorusu            |
|                                                           |
|  output.data:                                             |
|  - Raw task sonuclari                                    |
|  - Dict: task_name -> {type, template, output}           |
|  - Detayli log ve debugging icin                         |
|                                                           |
|  ILISKI: values = data'dan cikarilmis ozet               |
|                                                           |
+----------------------------------------------------------+
```

### 4.3 Output Plugin Ornek (Tasker)

```python
class TaskerPlugin:
    """Output plugin ornegi"""

    def execute(self, services: PluginServices, job: Job) -> PluginResult:
        output_values = []
        task_results = {}  # Dict, array degil

        for task in self.config.tasks:
            # 1. Template render
            rendered = services.template.render(task.template, job)

            # 2. Task calistir
            if task.type == 'save':
                dest_path = services.template.render(task.path, job)
                success = self._save_file(job.input.value, dest_path)

                # 3. output.values'a ekle
                if success:
                    output_values.append(dest_path)

                # Dict key = task.name
                task_results[task.name] = {
                    'type': 'save',
                    'template': task.path,
                    'output': dest_path
                }

            elif task.type == 'print':
                task_results[task.name] = {
                    'type': 'print',
                    'template': task.template,
                    'output': rendered
                }

        # 4. output.values kaydet
        services.state.set_output_values(job.id, output_values)

        # 5. output.data kaydet
        output_data = {'tasks': task_results}
        services.state.set_output_data(job.id, output_data)

        # 6. Plugin data kaydet (ayni data)
        services.state.update_plugin_data(
            job_id=job.id,
            plugin_name='tasker',
            data=output_data
        )

        return PluginResult(success=True)
```

---

## 5. PARSE VE DATA PHASE KURALLARI

### 5.1 Dosya Kaydetme Yasagi

```
+----------------------------------------------------------+
|              PHASE KURALLARI                              |
+----------------------------------------------------------+
|                                                           |
|  INPUT PHASE:                                             |
|  - Job olusturur                                         |
|  - input.value, input.data doldurur                      |
|  - Dosya okuyabilir (tarama)                             |
|  - Dosya KAYDETMEZ                                       |
|                                                           |
|  PARSE PHASE:                                             |
|  - Dosya adi parse eder                                  |
|  - Metadata cikarir                                      |
|  - Dosya KAYDETMEZ                                       |
|                                                           |
|  DATA PHASE:                                              |
|  - External API cagirir                                  |
|  - Metadata zenginlestirir                               |
|  - Cache dosyasi KAYDEDEBILIR (ornek: ffprobe)          |
|  - Ana cikti dosyasi KAYDETMEZ                          |
|                                                           |
|  OUTPUT PHASE:                                            |
|  - Dosya kopyalar/tasir                                  |
|  - NFO/poster/subtitle kaydeder                          |
|  - output.values doldurur                                |
|  - Ana cikti dosyalarini KAYDEDER                       |
|                                                           |
+----------------------------------------------------------+
```

### 5.2 ffprobe Ornegi (Data Phase Cache)

```
+----------------------------------------------------------+
|              CACHE VS OUTPUT                              |
+----------------------------------------------------------+
|                                                           |
|  ffprobe (DATA phase):                                   |
|  - Media info cache dosyasi kaydeder                     |
|  - Bu cache, performans icin                             |
|  - output.values'a EKLENMEZ                              |
|  - Kullanici ciktisi DEGIL                               |
|                                                           |
|  tasker (OUTPUT phase):                                   |
|  - Film dosyasini kopyalar                               |
|  - NFO dosyasi olusturur                                 |
|  - output.values'a EKLENIR                               |
|  - Kullanici ciktisi EVET                                |
|                                                           |
+----------------------------------------------------------+
```

---

## 6. DATA DUPLICATION - ISLENMIS VS RAW

### 6.1 Neden Iki Yerde?

```
+----------------------------------------------------------+
|              DATA DUPLICATION                             |
+----------------------------------------------------------+
|                                                           |
|  output.data:                                             |
|  - Sistem tarafindan KNOWN lokasyon                      |
|  - Hizli erisim: job.output.data.tasks                   |
|  - Query: "Bu job'un task sonuclari ne?"                 |
|                                                           |
|  plugins.tasker:                                          |
|  - Plugin-specific lokasyon                              |
|  - Tutarlilik: Her plugin kendi namespace'inde           |
|  - Query: "Tasker ne yapti?"                             |
|                                                           |
|  TEKRAR DEGIL:                                            |
|  - Farkli erisim pattern'leri                            |
|  - output.* = sistem perspective                         |
|  - plugins.* = plugin perspective                        |
|                                                           |
+----------------------------------------------------------+
```

### 6.2 Islenmis vs Raw

```
+----------------------------------------------------------+
|              ISLENMIS VS RAW                              |
+----------------------------------------------------------+
|                                                           |
|  output.values (ISLENMIS):                                |
|  - Sadece cikti path'leri                                |
|  - Array of strings                                      |
|  - Veritabani indexleme icin optimize                    |
|                                                           |
|  output.data (RAW):                                       |
|  - Tum task detaylari                                    |
|  - Dict: task_name -> {type, template, output}           |
|  - Debugging ve logging icin                             |
|                                                           |
|  ORNEK:                                                   |
|  values: ["/path/a.mkv", "/path/a.nfo"]                  |
|  data:                                                   |
|    tasks:                                                |
|      save_movie: {type: save, output: /path/a.mkv}       |
|      create_nfo: {type: save, output: /path/a.nfo}       |
|                                                           |
+----------------------------------------------------------+
```

---

## 7. TEMPLATE ERISIM

### 7.1 Yeni Erisim Pattern'leri

```jinja2
{# INPUT #}
{{ job.input.value }}                    {# Eski: job.input.path #}
{{ job.input.data.filename }}
{{ job.input.data.extension }}

{# OUTPUT #}
{{ job.output.values }}                  {# Array #}
{{ job.output.values[0] }}               {# Ilk cikti #}
{{ job.output.data.tasks }}              {# Task dict #}
{{ job.output.data.tasks.save_movie }}   {# Spesifik task #}

{# PLUGINS #}
{{ job.plugins.scanner.filename }}
{{ job.plugins.tmdb.status.success }}
{{ job.plugins.tmdb.movie.title }}
{{ job.plugins.tasker.tasks }}
```

---

## 8. STATE MANAGER API

```python
class StateManager:
    """Yeni input/output API"""

    def create_job(
        self,
        input_value: str,
        input_data: Optional[Dict] = None
    ) -> Job:
        """Input plugin tarafindan cagirilir"""
        job = Job(
            id=uuid4(),
            input=InputSection(
                value=input_value,
                data=input_data or {}
            ),
            output=OutputSection(
                values=[],
                data={}
            ),
            plugins={}
        )
        self._jobs[job.id] = job
        return job

    def set_output_values(self, job_id: str, values: List[str]) -> None:
        """Output plugin tarafindan cagirilir"""
        self._jobs[job_id].output.values = values

    def add_output_value(self, job_id: str, value: str) -> None:
        """Tek cikti ekle"""
        self._jobs[job_id].output.values.append(value)

    def set_output_data(self, job_id: str, data: Dict) -> None:
        """Output plugin tarafindan cagirilir"""
        self._jobs[job_id].output.data = data

    def update_plugin_data(
        self,
        job_id: str,
        plugin_name: str,
        data: Dict
    ) -> None:
        """Tum pluginler tarafindan cagirilir"""
        self._jobs[job_id].plugins[plugin_name] = data
```

**Uyari:** Ornek kod, yaklasimi gosterir. Execution session'da mevcut codebase'e uyarlanmalidir.

---

## 9. MIGRATION: path -> value

```
+----------------------------------------------------------+
|              MIGRATION                                    |
+----------------------------------------------------------+
|                                                           |
|  ESKI                          YENI                       |
|  ----------------------------------------------------------
|  job.input.path               job.input.value            |
|  job.output.paths             job.output.values          |
|  (yok)                        job.input.data             |
|  (yok)                        job.output.data            |
|                                                           |
+----------------------------------------------------------+
```

---

## 10. SONUC

```
+----------------------------------------------------------+
|              FINAL YAPI                                   |
+----------------------------------------------------------+
|                                                           |
|  INPUT SECTION:                                           |
|  - value: Fiziksel veya virtual girdi                    |
|  - data: Input plugin'in ek datasi                       |
|                                                           |
|  OUTPUT SECTION:                                          |
|  - values: Cikti path'leri/degerleri (array)             |
|  - data: Output plugin'in raw datasi                     |
|                                                           |
|  PLUGINS SECTION:                                         |
|  - Her plugin kendi namespace'inde                       |
|  - input/output data AYNI data burada da var             |
|                                                           |
|  PHASE KURALLARI:                                         |
|  - input: Job olustur, value+data doldur                 |
|  - parse/data: Analiz, dosya KAYDETME (cache haric)      |
|  - output: Cikti olustur, values+data doldur             |
|                                                           |
+----------------------------------------------------------+
```

---

**Son Guncelleme:** 2025-12-03
