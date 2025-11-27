# DATABASE ARCHITECTURE & COLLECTION DESIGN

**Version**: 1.0.0  
**Date**: 2025-11-26  
**Status**: Planning Phase  
**Author**: Architecture Analysis

---

## 📊 EXECUTIVE SUMMARY

Bu döküman, Archiverr projesi için endüstri seviyesinde bir veritabanı mimarisi planı sunmaktadır. MongoDB entegrasyonu öncesinde:

1. **Klasör Yapısı Analizi** - `persistence/` vs `infrastructure/` vs `db/`
2. **Collection Tasarımı** - Veri modelleri ve ilişkileri
3. **Mock Üzerinde Test** - MongoDB öncesi validasyon
4. **Geçiş Stratejisi** - Adım adım entegrasyon

---

## 🔍 ENDÜSTRİ ARAŞTIRMASI

### Klasör İsimlendirme Karşılaştırması

| İsim | Kullanım | Avantaj | Dezavantaj |
|------|----------|---------|------------|
| **`infrastructure/`** | Clean Architecture, Sonarr-like | Endüstri standardı, geniş kapsam | Uzun isim |
| `persistence/` | Sadece DB | Spesifik, anlaşılır | Dar kapsam (sadece DB) |
| `db/` | Basit projeler | Kısa | Belirsiz, çok genel |
| `data/` | Data processing | Esnek | DB ile karışır |
| `repositories/` | DDD projeler | Pattern-specific | Sadece repo |
| `adapters/` | Ports & Adapters | Hexagonal arch | Karmaşık |

### Endüstri Referansları

```
# Sonarr (C#)
NzbDrone.Core/
├── Datastore/          # Database access
│   ├── Migration/      # DB migrations
│   └── Repository/     # Repository pattern
├── Jobs/               # Background jobs
└── Providers/          # External services

# FastAPI Clean Architecture (Python)
app/
├── domain/             # Business logic
│   └── interfaces/     # Repository interfaces
├── application/        # Use cases
├── infrastructure/     # Technical implementations
│   ├── repositories/   # DB repositories
│   └── services/       # External services
└── presentation/       # API layer

# Cosmic Python (Book Standard)
src/
├── domain/             # Entities, value objects
├── adapters/           # External system adapters
│   ├── orm.py          # SQLAlchemy
│   └── repository.py   # Repository impl
└── service_layer/      # Application services
```

### 🎯 KARAR: `infrastructure/` Kullanımı

**Neden?**

1. **Clean Architecture standardı** - En yaygın kabul gören pattern
2. **Geniş kapsam** - Sadece DB değil, tüm external services
3. **Gelecek proofing** - FastAPI, cache, queue eklenebilir
4. **Sonarr/Radarr benzeri** - Media uygulamalarında yaygın

---

## 🏗️ ÖNERİLEN KLASÖR YAPISI

### Mevcut Yapı (Değiştirilecek)

```
src/archiverr/
├── persistence/        # ❌ Dar kapsam, sadece DB
│   ├── interface.py
│   ├── mock.py
│   └── mongodb.py
├── state/              # ✅ Kalacak
├── events/             # ✅ Kalacak
└── ...
```

### Önerilen Yapı

```
src/archiverr/
├── infrastructure/                    # 🆕 Tüm technical implementations
│   ├── __init__.py
│   │
│   ├── database/                      # Database layer
│   │   ├── __init__.py
│   │   ├── interface.py               # Abstract base (PersistenceInterface)
│   │   ├── mock.py                    # JSON file-based mock
│   │   ├── mongodb.py                 # MongoDB implementation
│   │   └── models.py                  # Pydantic/Beanie models (gelecek)
│   │
│   ├── repositories/                  # Repository pattern
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseRepository abstract
│   │   ├── execution_repository.py   # ExecutionState CRUD
│   │   ├── match_repository.py       # MatchState CRUD
│   │   └── plugin_result_repository.py
│   │
│   └── services/                      # External services (gelecek)
│       ├── __init__.py
│       └── cache.py                   # Redis cache (opsiyonel)
│
├── state/                             # State management (MEVCUT)
│   ├── manager.py                     # GlobalStateManager
│   └── models.py                      # State dataclasses
│
├── events/                            # Event bus (MEVCUT)
│   ├── bus.py
│   └── handlers.py
│
└── ...
```

---

## 📦 COLLECTION DESIGN (MongoDB)

### Veri Akışı Analizi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXECUTION LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐      │
│   │  EXECUTION  │────▶│   MATCHES   │────▶│    PLUGIN_RESULTS      │      │
│   │  (1 per run)│     │ (N per exec)│     │ (M per match per plugin)│      │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘      │
│         │                   │                        │                      │
│         │                   │                        │                      │
│         ▼                   ▼                        ▼                      │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐      │
│   │ Config      │     │ Task        │     │ Plugin Data             │      │
│   │ Snapshot    │     │ Results     │     │ (tmdb, renamer, etc.)   │      │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Collection 1: `executions`

**Amaç**: Her çalıştırma için metadata ve config snapshot

```javascript
{
  "_id": "exec_abc12345",          // Unique execution ID
  "id": "abc12345",                // Short ID (for display)
  
  // Timing
  "started_at": ISODate("2025-11-26T17:14:34.984Z"),
  "finished_at": ISODate("2025-11-26T17:14:42.520Z"),
  "duration_ms": 7536,
  
  // Status
  "status": "completed",           // pending | running | completed | failed
  "success": true,
  
  // Summary (denormalized for fast queries)
  "summary": {
    "total_matches": 2,
    "completed_matches": 2,
    "failed_matches": 0,
    "total_tasks": 14,
    "enabled_plugins": ["scanner", "ffprobe", "renamer", "tmdb", "omdb"]
  },
  
  // Config snapshot (for reproducibility)
  "config_snapshot": {
    "options": {
      "debug": true,
      "dry_run": true,
      "hardlink": true
    },
    "plugins": {
      "scanner": { "enabled": true },
      "tmdb": { "enabled": true },
      // ... only enabled status, not full config (security)
    },
    "tasks": [
      // Task definitions (names only, not templates)
      { "name": "print_match_header", "type": "print" },
      { "name": "save_nfo", "type": "save" }
    ]
  },
  
  // Metadata
  "created_at": ISODate("2025-11-26T17:14:34.984Z"),
  "updated_at": ISODate("2025-11-26T17:14:42.520Z"),
  "version": "2.1.0"               // Archiverr version
}
```

**Indexes**:
```javascript
db.executions.createIndex({ "started_at": -1 })           // Recent executions
db.executions.createIndex({ "status": 1, "started_at": -1 }) // By status
db.executions.createIndex({ "success": 1 })               // Failed executions
```

### Collection 2: `matches`

**Amaç**: Her match için özet bilgi (plugin detayları ayrı collection'da)

```javascript
{
  "_id": "match_0_abc12345",       // Composite: match_{index}_{execution_id}
  "execution_id": "exec_abc12345", // FK reference
  "index": 0,                      // Match index (0-based)
  
  // Input info
  "input_path": "/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv",
  "category": "movie",             // movie | show | unknown
  
  // Status
  "status": "completed",           // pending | running | completed | failed
  "success": true,
  
  // Timing
  "started_at": ISODate("2025-11-26T17:14:34.990Z"),
  "finished_at": ISODate("2025-11-26T17:14:37.520Z"),
  "duration_ms": 2530,
  
  // Plugin execution summary (denormalized)
  "plugins_summary": {
    "executed": ["scanner", "ffprobe", "renamer", "tmdb", "omdb", "tvdb"],
    "failed": [],
    "skipped": ["tvmaze"]          // Not supported for this category
  },
  
  // Task results (embedded, small data)
  "tasks": [
    {
      "name": "print_match_header",
      "type": "print",
      "success": true,
      "executed_at": ISODate("2025-11-26T17:14:37.510Z")
    },
    {
      "name": "save_nfo",
      "type": "save",
      "success": true,
      "destination": "/output/movies/Mr. & Mrs. Smith (2005)/movie.nfo"
    }
  ],
  
  // Metadata
  "created_at": ISODate("2025-11-26T17:14:34.990Z")
}
```

**Indexes**:
```javascript
db.matches.createIndex({ "execution_id": 1, "index": 1 }, { unique: true })
db.matches.createIndex({ "execution_id": 1 })             // All matches for exec
db.matches.createIndex({ "category": 1 })                 // By category
db.matches.createIndex({ "success": 1 })                  // Failed matches
```

### Collection 3: `plugin_results`

**Amaç**: Detaylı plugin çıktıları (büyük veri, ayrı collection)

```javascript
{
  "_id": "pr_tmdb_0_abc12345",     // Composite: pr_{plugin}_{match}_{exec}
  "execution_id": "exec_abc12345", // FK reference
  "match_id": "match_0_abc12345",  // FK reference
  "match_index": 0,                // For fast filtering
  "plugin_name": "tmdb",
  
  // Plugin status
  "status": {
    "success": true,
    "started_at": ISODate("2025-11-26T17:14:35.100Z"),
    "finished_at": ISODate("2025-11-26T17:14:36.300Z"),
    "duration_ms": 1200
  },
  
  // Plugin data (opaque to core - plugin owns structure)
  "data": {
    "movie": {
      "id": 787,
      "title": "Bay ve Bayan Smith",
      "original_title": "Mr. & Mrs. Smith",
      "year": 2005,
      "runtime": 120,
      "genres": ["Action", "Comedy", "Romance"],
      "overview": "...",
      "poster_path": "/...",
      "backdrop_path": "/...",
      // ... full TMDb data
    },
    "credits": {
      "cast": [...],
      "crew": [...]
    },
    "images": {
      "posters": [...],
      "backdrops": [...]
    },
    "validation": {
      "duration_match": true,
      "tests_passed": 1,
      "tests_total": 1
    }
  },
  
  // Metadata
  "created_at": ISODate("2025-11-26T17:14:36.300Z"),
  
  // TTL için (90 gün sonra otomatik sil)
  "expires_at": ISODate("2026-02-24T17:14:36.300Z")
}
```

**Indexes**:
```javascript
db.plugin_results.createIndex({ "execution_id": 1, "match_index": 1, "plugin_name": 1 })
db.plugin_results.createIndex({ "match_id": 1 })           // All plugins for match
db.plugin_results.createIndex({ "plugin_name": 1 })        // By plugin type
db.plugin_results.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 }) // TTL
```

### Collection 4: `branches` (Git-like Versioning)

**Amaç**: Named references for execution history tracking

```javascript
{
  "_id": "branch_abc12345",           // Unique branch ID
  "name": "production",               // Branch name (unique)
  "description": "Production runs",   // Optional description
  "is_default": true,                 // Default branch flag
  "head_commit_id": "commit_xyz789",  // Latest commit reference
  "created_at": ISODate("2025-11-26T17:14:34.984Z"),
  "updated_at": ISODate("2025-11-26T18:20:00.000Z")
}
```

**Indexes**:
```javascript
db.branches.createIndex({ "name": 1 }, { unique: true })  // Unique branch names
db.branches.createIndex({ "created_at": 1 })              // Sort by creation
db.branches.createIndex({ "is_default": 1 })              // Find default branch
```

### Collection 5: `commits` (Git-like Versioning)

**Amaç**: Immutable snapshots linking executions to branches

```javascript
{
  "_id": "commit_xyz789",             // Unique commit ID
  "branch_id": "branch_abc12345",     // FK to branches
  "execution_id": "exec_abc12345",    // FK to executions
  "parent_commit_id": "commit_prev",  // Previous commit (linked list)
  "message": "Added new media files", // Commit message
  "metadata": {                       // Optional metadata
    "tags": ["movies", "2025"]
  },
  "created_at": ISODate("2025-11-26T17:14:42.520Z"),
  
  // Snapshot of execution summary at commit time
  "execution_summary": {
    "status": "completed",
    "success": true,
    "total_matches": 2,
    "completed_matches": 2,
    "failed_matches": 0
  }
}
```

**Indexes**:
```javascript
db.commits.createIndex({ "branch_id": 1 })                         // All commits on branch
db.commits.createIndex({ "execution_id": 1 })                      // Find by execution
db.commits.createIndex({ "branch_id": 1, "created_at": -1 })       // Latest commits on branch
db.commits.createIndex({ "parent_commit_id": 1 })                  // Traverse history
```

---

## 🔗 VERİ İLİŞKİLERİ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RELATIONSHIP DIAGRAM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  branches (1)                                                                │
│      │                                                                       │
│      │ branch_id                                                             │
│      ▼                                                                       │
│  commits (N) ─────────────────────────────▶ executions (1)                  │
│      │                                            │                          │
│      │ parent_commit_id                           │ execution_id             │
│      │ (linked list)                              │                          │
│      ▼                                            ├──────▶ matches (N)       │
│  [commit_history]                                 │           │              │
│                                                   │           │ match_id     │
│                                                   │           │              │
│                                                   └───────────┼───▶ plugin_results (M×P)
│                                                               │              │
│                                                               └──────────────┘
│                                                                              │
│  Legend:                                                                     │
│  - N = number of items                                                       │
│  - M = number of matches                                                     │
│  - P = number of plugins per match                                          │
│                                                                              │
│  Git-like Flow:                                                              │
│  branch → commit → execution → matches → plugin_results                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Query Patterns

```javascript
// 1. Get execution with all matches
db.executions.aggregate([
  { $match: { _id: "exec_abc12345" } },
  { $lookup: {
      from: "matches",
      localField: "_id",
      foreignField: "execution_id",
      as: "matches"
  }}
])

// 2. Get match with all plugin results
db.matches.aggregate([
  { $match: { _id: "match_0_abc12345" } },
  { $lookup: {
      from: "plugin_results",
      localField: "_id",
      foreignField: "match_id",
      as: "plugins"
  }}
])

// 3. Get recent failed executions
db.executions.find({
  success: false,
  started_at: { $gte: ISODate("2025-11-01") }
}).sort({ started_at: -1 })

// 4. Get all movies processed
db.matches.find({
  category: "movie"
}).sort({ created_at: -1 })

// 5. Get TMDb data for all matches in execution
db.plugin_results.find({
  execution_id: "exec_abc12345",
  plugin_name: "tmdb"
})

// 6. Git-like: List all branches
db.branches.find().sort({ created_at: -1 })

// 7. Git-like: Get commits on a branch
db.commits.find({ branch_id: "branch_abc12345" }).sort({ created_at: -1 })

// 8. Git-like: Get commit history (traverse parent links)
// Note: This requires application-level traversal or $graphLookup
db.commits.aggregate([
  { $match: { _id: "commit_xyz789" } },
  { $graphLookup: {
      from: "commits",
      startWith: "$parent_commit_id",
      connectFromField: "parent_commit_id",
      connectToField: "_id",
      as: "history"
  }}
])

// 9. Git-like: Checkout - get full execution data for a commit
db.commits.aggregate([
  { $match: { _id: "commit_xyz789" } },
  { $lookup: {
      from: "executions",
      localField: "execution_id",
      foreignField: "_id",
      as: "execution"
  }},
  { $lookup: {
      from: "matches",
      localField: "execution_id",
      foreignField: "execution_id",
      as: "matches"
  }},
  { $lookup: {
      from: "plugin_results",
      localField: "execution_id",
      foreignField: "execution_id",
      as: "plugin_results"
  }}
])
```

---

## 📋 MOCK TEST PLANI

MongoDB öncesi mock üzerinde test edilecek senaryolar:

### Test 1: Basic CRUD

```python
# test_mock_crud.py

def test_execution_lifecycle():
    """Test execution create/update/complete"""
    persistence = MockPersistence("./test_db")
    persistence.connect()
    
    # Create execution
    exec_state = ExecutionState(id="test1", ...)
    persistence.save_execution(exec_state)
    
    # Verify
    retrieved = persistence.get_execution("test1")
    assert retrieved["id"] == "test1"
    
    # Update
    exec_state.status = ExecutionStatus.COMPLETED
    persistence.save_execution(exec_state)
    
    # Verify update
    retrieved = persistence.get_execution("test1")
    assert retrieved["status"] == "completed"
    
    persistence.disconnect()
```

### Test 2: Match-Plugin Relationship

```python
def test_match_with_plugins():
    """Test match with multiple plugin results"""
    persistence = MockPersistence("./test_db")
    persistence.connect()
    
    # Create match
    match = MatchState(index=0, input_path="/test.mkv", ...)
    persistence.save_match(match)
    
    # Add plugin results
    persistence.save_plugin_result("exec1", 0, "tmdb", {...})
    persistence.save_plugin_result("exec1", 0, "omdb", {...})
    
    # Verify all plugins retrieved
    plugins = persistence.get_plugin_results("exec1", 0)
    assert "tmdb" in plugins
    assert "omdb" in plugins
    
    persistence.disconnect()
```

### Test 3: Query Performance

```python
def test_query_performance():
    """Test query performance with many records"""
    persistence = MockPersistence("./test_db")
    persistence.connect()
    
    # Create 1000 matches
    for i in range(1000):
        match = MatchState(index=i, ...)
        persistence.save_match(match)
    
    # Time query
    import time
    start = time.time()
    matches = persistence.get_matches("exec1")
    duration = time.time() - start
    
    assert len(matches) == 1000
    assert duration < 1.0  # Should be fast
    
    persistence.disconnect()
```

---

## 🚀 GEÇİŞ STRATEJİSİ

### Phase 1: Klasör Restructure (HEMEN)

1. `persistence/` → `infrastructure/database/` taşı
2. `__init__.py` import'ları güncelle
3. `__main__.py` import'ları güncelle
4. Test: Syntax check + run

### Phase 2: Repository Pattern (SONRA)

1. `BaseRepository` abstract class oluştur
2. `ExecutionRepository`, `MatchRepository` implemente et
3. `GlobalStateManager`'ı repository kullanacak şekilde güncelle
4. Test: Mevcut testler geçiyor mu?

### Phase 3: Mock Validation (SONRA)

1. Collection yapısını mock'a implemente et
2. Query pattern'leri test et
3. Performance benchmark
4. Test: 1000+ match senaryosu

### Phase 4: MongoDB Integration (EN SON)

1. `MongoDBRepository` implementations
2. Connection pooling
3. Index creation
4. Test: Production-like load

---

## ✅ CHECKLIST

- [ ] Klasör yapısı onaylandı
- [ ] Collection design review edildi
- [ ] Mock üzerinde test edildi
- [ ] Query patterns doğrulandı
- [ ] Performance acceptable
- [ ] MongoDB integration hazır

---

## 📚 REFERENCES

- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Cosmic Python - Repository Pattern](https://www.cosmicpython.com/book/chapter_02_repository.html)
- [MongoDB Data Modeling](https://www.mongodb.com/docs/manual/core/data-modeling-introduction/)
- [FastAPI Clean Architecture](https://github.com/movassaghi6/fastapi-clean-mongo)
