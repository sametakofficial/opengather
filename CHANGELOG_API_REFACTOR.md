# API Refactor Changelog - Motor/FastAPI Event Loop Fix

**Tarih**: 2025-11-27  
**Amaç**: Motor (async MongoDB driver) ve FastAPI arasındaki event loop çakışmasını endüstri standartlarına uygun şekilde çözmek.

---

## Problem Tanımı

### Orijinal Sorun
FastAPI async endpoint'leri içinde Motor async driver kullanıldığında şu hata alınıyordu:
```
RuntimeError: Cannot run the event loop while another loop is running
```

**Sebep**: Motor client'ı bir event loop'a bağlıyken, FastAPI kendi event loop'unda çalışıyor. İki farklı async context çakışıyordu.

### Önceki (Yanlış) Çözüm
- Endpoint'ler skip edilmişti (executions, matches, versioning)
- PyMongo (sync) ile geçici çözüm denenmiş ama iki ayrı bağlantı sistemi oluşmuştu

---

## Uygulanan Çözüm: Lifespan Pattern

### Referans Kaynaklar
1. FastAPI GitHub Discussions #13029 - "How appropriate is it to store database client in lifespan state?"
2. FastAPI Collaborator YuriiMotov'un önerisi: `request.state.db` pattern
3. Starlette Lifespan documentation

### Çözüm Mantığı
Motor client'ı FastAPI lifespan içinde oluşturulursa, aynı event loop'u paylaşır. Bu şekilde çakışma olmaz.

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI App                       │
│  ┌───────────────────────────────────────────────┐  │
│  │           Lifespan Context Manager             │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  Motor Client (AsyncIOMotorClient)      │  │  │
│  │  │  - Aynı event loop                      │  │  │
│  │  │  - app.state.db'ye kaydedilir           │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  │                     │                          │  │
│  │                     ▼                          │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  Endpoint'ler request.app.state.db ile  │  │  │
│  │  │  async olarak MongoDB'ye erişir         │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Dosya Değişiklikleri

### 1. YENİ DOSYA: `src/archiverr/api/database.py`

**Amaç**: MongoDB bağlantı yönetimini merkezi bir modülde toplamak.

```python
# Singleton pattern ile MongoDB bağlantısı
class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls) -> AsyncIOMotorDatabase:
        cls.client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50,  # Connection pool
            minPoolSize=5,
        )
        cls.db = cls.client[database]
        await cls.db.command("ping")  # Bağlantı doğrulama
        return cls.db
    
    @classmethod
    async def disconnect(cls) -> None:
        if cls.client is not None:
            cls.client.close()


# FastAPI lifespan context manager
@asynccontextmanager
async def mongodb_lifespan(app):
    # Startup
    db = await MongoDB.connect()
    app.state.db = db  # App state'e kaydet
    yield
    # Shutdown
    await MongoDB.disconnect()
```

**Kritik Noktalar**:
- `AsyncIOMotorClient` parametreleri: timeout ve pool size production-ready değerler
- `app.state.db` kullanımı: FastAPI'nin önerdiği pattern
- Context manager: Otomatik cleanup garantisi

---

### 2. DEĞİŞİKLİK: `src/archiverr/api/main.py`

**Önceki Durum** (satır 33-43):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup - nothing to do
    yield
    # Shutdown - nothing to cleanup
```

**Yeni Durum**:
```python
from .database import mongodb_lifespan

def create_app() -> FastAPI:
    app = FastAPI(
        title="Archiverr API",
        lifespan=mongodb_lifespan,  # Lifespan pattern
        ...
    )
```

**Ek Düzeltme** (satır 85-88):
```python
# ÖNCE (Hatalı):
rate_limiter = RateLimiter(
    requests_per_minute=int(...),  # Yanlış parametre
    burst_size=int(...)
)
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

# SONRA (Doğru):
limiter = RateLimiter()  # Config objesi alır, bireysel parametreler değil
app.add_middleware(RateLimitMiddleware, limiter=limiter)  # 'limiter' parametresi
```

**Hata Sebebi**: RateLimiter.__init__() sadece `config: Optional[RateLimitConfig]` alıyor, `requests_per_minute` gibi parametreler yok.

---

### 3. DEĞİŞİKLİK: `src/archiverr/api/v1/executions/router.py`

**Önceki Durum** (Sync PyMongo):
```python
from archiverr.api.dependencies import get_sync_db

def _get_db():
    db = get_sync_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db

@router.get("/")
def list_executions(...):  # sync fonksiyon
    db = _get_db()
    cursor = db["executions"].find()  # sync cursor
    executions = list(cursor)  # list() ile sync iteration
```

**Yeni Durum** (Async Motor):
```python
def _get_db(request: Request):
    """Get database from app state (set by lifespan)."""
    db = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db

@router.get("/")
async def list_executions(request: Request, ...):  # async fonksiyon
    db = _get_db(request)
    cursor = db["executions"].find().sort("started_at", -1).skip(offset).limit(limit)
    executions = await cursor.to_list(length=limit)  # async to_list()
    total = await db["executions"].count_documents({})  # async count
```

**Kritik Farklar**:
1. `def` → `async def` (tüm endpoint'ler)
2. `request: Request` parametresi eklendi (app.state erişimi için)
3. `list(cursor)` → `await cursor.to_list(length=limit)` (async iteration)
4. `db.count_documents({})` → `await db.count_documents({})` (async)

---

### 4. DEĞİŞİKLİK: `src/archiverr/api/v1/matches/router.py`

**Aynı pattern uygulandı**:

```python
# Önceki
def _get_db():
    db = get_sync_db()
    ...

@router.get("/")
def list_matches(...):
    db = _get_db()
    cursor = db["matches"].find(query)
    matches = list(cursor)

# Yeni
def _get_db(request: Request):
    db = request.app.state.db
    ...

@router.get("/")
async def list_matches(request: Request, ...):
    db = _get_db(request)
    cursor = db["matches"].find(query).sort("created_at", -1).skip(offset).limit(limit)
    matches = await cursor.to_list(length=limit)
```

---

### 5. DEĞİŞİKLİK: `src/archiverr/api/v1/versioning/router.py`

**Aynı pattern + datetime dönüşüm düzeltmesi**:

```python
def _to_iso_string(val) -> str:
    """Convert datetime or any value to ISO string."""
    if val is None:
        return ""
    if hasattr(val, 'isoformat'):  # datetime objesi kontrolü
        return val.isoformat()
    return str(val)
```

**Neden Gerekli**: MongoDB datetime objesi döndürür, Pydantic model string bekler. Dönüşüm yapılmazsa:
```
ValidationError: Input should be a valid string [type=string_type, 
input_value=datetime.datetime(2025, 1... 26, 22, 18, 28, 421000)]
```

---

### 6. DEĞİŞİKLİK: `src/archiverr/api/v1/router.py`

**Değişiklik yok** - Router zaten doğru yapılandırılmıştı:
```python
router.include_router(executions_router, prefix="/executions", tags=["Executions"])
router.include_router(matches_router, prefix="/matches", tags=["Matches"])
router.include_router(versioning_router, prefix="/versioning", tags=["Versioning"])
```

---

### 7. DEĞİŞİKLİK: `tests/test_api.py`

**Önceki Durum** (satır 22-26):
```python
@pytest.fixture
def client():
    from archiverr.api.main import app
    return TestClient(app)  # Lifespan çalışmaz!
```

**Yeni Durum**:
```python
@pytest.fixture
def client():
    from archiverr.api.main import app
    with TestClient(app) as c:  # Context manager - lifespan çalışır
        yield c
```

**Kritik Fark**: 
- `TestClient(app)` - Lifespan event'leri çalışmaz, `app.state.db` set edilmez
- `with TestClient(app) as c:` - Lifespan startup/shutdown çalışır

Hata mesajı (düzeltmeden önce):
```
AttributeError: 'State' object has no attribute 'db'
```

---

## Silinen/Kullanılmayan Kod

### `src/archiverr/api/dependencies.py` içindeki `get_sync_db()`

Bu fonksiyon artık kullanılmıyor çünkü tüm endpoint'ler async Motor kullanıyor. Dosya hala mevcut ama `get_sync_db()` çağrılmıyor.

---

## Test Sonuçları

```
============================= 130 passed in 47.35s =============================
```

Önceki durum: 4 test skip ediliyordu (executions, matches, versioning endpoint'leri)
Şimdiki durum: 0 skip, 130 passed

---

## Doğrulama Komutları

```bash
# API'yi başlat
python -m archiverr serve --port 8000

# Endpoint'leri test et
curl http://localhost:8000/api/v1/executions/
curl http://localhost:8000/api/v1/matches/
curl http://localhost:8000/api/v1/versioning/branches

# Testleri çalıştır
python -m pytest tests/test_api.py -v
```

---

## Özet Tablo

| Dosya | Değişiklik Tipi | Açıklama |
|-------|-----------------|----------|
| `api/database.py` | YENİ | MongoDB singleton + lifespan context manager |
| `api/main.py` | GÜNCELLEME | `lifespan=mongodb_lifespan` + middleware param fix |
| `api/v1/executions/router.py` | YENİDEN YAZILDI | sync → async, PyMongo → Motor |
| `api/v1/matches/router.py` | YENİDEN YAZILDI | sync → async, PyMongo → Motor |
| `api/v1/versioning/router.py` | YENİDEN YAZILDI | sync → async + datetime fix |
| `tests/test_api.py` | GÜNCELLEME | TestClient context manager |

---

## Teknik Referanslar

1. **Motor Documentation**: https://motor.readthedocs.io/en/stable/
2. **FastAPI Lifespan**: https://fastapi.tiangolo.com/advanced/events/
3. **Starlette State**: https://www.starlette.io/applications/#storing-state-on-the-app-instance
4. **AsyncIOMotorClient**: Motor client'ı oluşturulduğu event loop'a bağlıdır
