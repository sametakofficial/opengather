# 🚀 ARCHIVERR ÇALIŞTIRMA REHBERİ

Terminal komutlarından output gelmiyor gibi görünüyor. Senin terminalinde şunu çalıştır:

## Hızlı Test

```bash
cd /home/samet/Workspace/archiverr
./QUICK_TEST.sh
```

Ya da manuel:

## Manuel Test

### 1. Python Test

```bash
cd /home/samet/Workspace/archiverr
python --version
```

### 2. Import Test

```bash
python -c "import sys; sys.path.insert(0, 'src'); from archiverr.utils.debug import init_debugger; print('Import OK')"
```

### 3. Config Test

```bash
python -c "import sys; sys.path.insert(0, 'src'); from archiverr.utils.config_loader import load_config_with_tracking; c = load_config_with_tracking('config.yml'); print(f'Config: {len(c)} keys')"
```

### 4. Archiverr Çalıştır

```bash
python -m archiverr
```

### 5. Verbose Test (Her şeyi göster)

```bash
python -m archiverr 2>&1 | tee archiverr.log
```

## Beklenen Output (INFO level)

```
2025-12-09T23:45:00+03:00  INFO   system               Archiverr starting (Session 11 - 4-stage architecture)
2025-12-09T23:45:00+03:00  INFO   scanner              Scanning target path=/tmp/test_movies/The.Matrix.1999.1080p.mkv
2025-12-09T23:45:00+03:00  INFO   scanner              Found file path=/tmp/test_movies/The.Matrix.1999.1080p.mkv size_mb=...
2025-12-09T23:45:01+03:00  INFO   renamer              Parsing filename=The.Matrix.1999.1080p
2025-12-09T23:45:01+03:00  INFO   tmdb                 Searching TMDb for movie name=The Matrix year=1999
...
```

## Debug Mode (Eğer hiç output yoksa)

config.yml'de:

```yaml
options:
  log_level: DEBUG # Her şeyi göster!
```

Sonra:

```bash
python -m archiverr
```

## Alternatif: Direct Python

```bash
python test_direct.py
```

## Sorun Varsa

### Import Hatası

```bash
pip install -e .
```

### Path Sorunu

```bash
export PYTHONPATH=/home/samet/Workspace/archiverr/src:$PYTHONPATH
python -m archiverr
```

### Verbose Her Şey

```bash
python -u -m archiverr 2>&1 | cat
```

## Terminal'den Çalıştır!

Ben terminal komutlarından output alamıyorum. SEN terminalinde çalıştır ve sonucu söyle! 💪
