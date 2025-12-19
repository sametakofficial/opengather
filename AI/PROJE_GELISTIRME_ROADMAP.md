# Archiverr Proje Geliştirme Roadmap

**Oluşturma Tarihi**: 2025-12-19  
**Durum**: Mevcut sorunlar ve yapılması gerekenler  

---

## KRİTİK SORUNLAR (Hemen Çözülmalı)

### 1. God Classes - Acil Refaktoring Gerekli

#### StageExecutor (902 satır)
**Sorun**: Tek sınıf çok fazla sorumluluk taşıyor
**Etkisi**: Bakım zor, test edilemez, değişiklik riskli
**Çözüm**:
```
- PluginExecutor (plugin çalıştırma)
- PluginValidator (doğrulama)  
- StateManager (durum yönetimi)
- ErrorHandler (hata yönetimi)
- ProgressTracker (ilerleme takibi)
```

#### Orchestrator (578 satır)
**Sorun**: Tüm workflow yönetimi tek sınıfta
**Çözüm**:
```
- WorkflowEngine (iş akışı motoru)
- PluginCoordinator (plugin koordinasyonu)
- ExecutionMonitor (çalıştırma monitörü)
- StatePersistence (durum kalıcılığı)
```

### 2. Dependency Injection Eksikliği

**Mevcut Durum**: Her yerde direkt object creation
**Sorun**: Test edilemez, esnek değil, tightly coupled
**Çözüm**:
```python
# DI Container ekle
class DIContainer:
    def register(self, interface, implementation)
    def resolve(self, interface)
    def inject(self, target_class)

# Interface'ler tanımla
class IDatabase(ABC)
class IStateService(ABC)
class IPluginLoader(ABC)
```

### 3. Exception Chaining (48 adet)

**Sorun**: `raise Error()` without `from e`
**Risk**: Debug zor, stack trace kaybolur
**Örnek Fix**:
```python
# Önceki hali
except Exception as e:
    raise ValueError("İşlem başarısız")

# Fix edilmiş hali  
except Exception as e:
    raise ValueError("İşlem başarısız") from e
```

---

## YÜKSEK ÖNCELİKLİ İYİLEŞTİRMELER

### 1. Logging Sistemi

**Mevcut Sorun**: `print()` statements production code'de
**Etkisi**: Loglama yok, monitoring imkansız
**Çözüm**:
```python
import structlog

logger = structlog.get_logger()

# Tüm print() yerlerini değiştir:
print("Başlatılıyor") → logger.info("Başlatılıyor")
print(f"Hata: {e}") → logger.error("Hata", error=str(e))
```

### 2. Input Validation

**Sorun**: API endpoint'ler validation olmadan kabul ediyor
**Risk**: Security açığı, data corruption
**Çözüm**:
```python
from pydantic import BaseModel, validator

class RunRequest(BaseModel):
    config: Dict[str, Any]
    dry_run: bool = False
    
    @validator('config')
    def validate_config(cls, v):
        # Validation logic
        return v
```

### 3. Configuration Management

**Sorun**: Hardcoded değerler
**Çözüm**:
```python
# environment-based config
class Settings(BaseSettings):
    mongodb_uri: str
    api_port: int = 8000
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
```

---

## ORTA ÖNCELİKLİ GELİŞTİRMELER

### 1. Test Coverage Artırımı

**Mevcut**: 420 test (mostly integration)
**Hedef**: 90% unit test coverage
**Plan**:
- Unit test'ler ekle (her class için)
- Mock kullanımı standartlaştır
- Test pyramid'i oluştur

### 2. Monitoring & Observability

**Eksik**: Metrics, tracing, health checks
**Çözüm**:
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests')
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')

# Health check endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

### 3. Error Handling Standardizasyonu

**Mevcut**: 84 adet `except Exception` 
**Hedef**: Specific exception handling
**Örnek**:
```python
# Önceki hali
except Exception as e:
    logger.error(f"Error: {e}")

# İyileştirilmiş hali
except DatabaseError as e:
    logger.error("Database error", details=str(e))
except ValidationError as e:
    logger.warning("Validation error", field=e.field)
except Exception as e:
    logger.error("Unexpected error", error=str(e))
    raise
```

---

## DÜŞÜK ÖNCELİKLİ İYİLEŞTİRMELER

### 1. Code Quality (911 ruff issues)

**Detay**:
- 827 W293 (blank-line-with-whitespace)
- 48 B904 (raise-without-from-inside-except)
- 14 ARG002 (unused-method-argument)
- 9 SIM105 (suppressible-exception)

**Otomatik Fix**:
```bash
# Auto-fix edilebilenler
ruff check --fix src/archiverr/

# Manual fix gerekenler
ruff check --select=B904 src/archiverr/
```

### 2. Documentation

**Eksik**: API docs, architecture docs
**Çözüm**:
- OpenAPI spec'i güncelle
- Architecture decision records (ADR)
- Developer setup guide

### 3. Performance Optimizasyonu

**Potansiyel**:
- Database connection pooling
- Async operations
- Caching layer

---

## UYGULAMA PLANI

### Hafta 1-2: Kriz Önlemleri
- [ ] Exception chaining fix (48 adet)
- [ ] Print → logger değişimi
- [ ] Acil security fix'ler

### Hafta 3-4: Architecture
- [ ] DI container implementasyonu
- [ ] Interface'ler tanımlama
- [ ] God class decomposition başlangıcı

### Hafta 5-6: Testing & Validation
- [ ] Pydantic models ekle
- [ ] Unit test'ler yaz
- [ ] Input validation

### Hafta 7-8: Monitoring
- [ ] Metrics ekle
- [ ] Health checks
- [ ] Structured logging

### Hafta 9-10: Code Quality
- [ ] Ruff issues temizleme
- [ ] Documentation
- [ ] Performance review

---

## GEREKLİ KAYNAKLAR

### Teknik
- Python 3.9+ features (type hints, async/await)
- FastAPI best practices
- MongoDB optimization
- Docker deployment

### Araçlar
- Dependency injection: `injector` veya `dependency-injector`
- Logging: `structlog`
- Validation: `pydantic`
- Testing: `pytest` + `pytest-asyncio`
- Monitoring: `prometheus-client`

### Eğitim
- Clean Architecture prensipleri
- SOLID principles
- Domain-driven design basics

---

## BAŞARI METRİKLERİ

### Teknik
- [ ] Test coverage > 90%
- [ ] 0 critical security issues
- [ ] All ruff issues resolved
- [ ] Build time < 30 seconds

### Kalite
- [ ] Max class size < 200 lines
- [ ] Max function size < 20 lines
- [ ] Cyclomatic complexity < 10
- [ ] 0 hardcoded configurations

### Performans
- [ ] API response time < 200ms
- [ ] Memory usage < 512MB
- [ ] 99.9% uptime

---

## RİSKLER

### Teknik
- Refactoring sırasında regression riski
- Database migration complexity
- Plugin system breaking changes

### Proje
- Scope creep (gereksiz özellikler)
- Technical debt accumulation
- Team learning curve

---

**Son Güncelleme**: 2025-12-19  
**Sorumlu**: Development Team  
**Review Tarihi**: Her 2 haftada bir
