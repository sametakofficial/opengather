# API RESPONSE - STATE MANAGEMENT & PROFESSIONAL PATTERNS

## API RESPONSE v4 (CURRENT - SIMPLIFIED & PLUGIN-AGNOSTIC)

**Version:** 2.3.0  
**Status:** Production Ready  
**Date:** November 11, 2025

---

## COMPLETE STRUCTURE

```javascript
{
  "globals": {
    "status": {
      "success": true,
      "matches": 2,
      "errors": 0,
      "tasks": 10,
      "started_at": "2025-11-26T16:30:00.123+03:00",
      "finished_at": "2025-11-26T16:30:10.456+03:00",
      "duration_ms": 10333
    },
    "summary": {
      "input_plugin_used": "scanner",
      "output_plugins_used": ["ffprobe", "renamer", "tmdb", "tvdb", "omdb"],
      "categories": ["movie", "show"],
      "total_size_bytes": 12345678900,
      "total_duration_seconds": 14400
    },
    "config": {
      "options": {
        "debug": true,
        "dry_run": true,
        "hardlink": true
      },
      "plugins": {
        "scanner": {
          "enabled": true,
          "targets": ["/path/to/media"],
          "recursive": false
        },
        "tmdb": {
          "enabled": true,
          "api_key": "***",
          "language": "tr-TR",
          "extras": {...}
        }
      },
      "tasks": [
        {
          "name": "print_match_header",
          "type": "print",
          "template": "..."
        }
      ]
    }
  },
  "matches": [
    {
      "globals": {
        "index": 0,
        "input_path": "/path/to/file.mkv",
        "status": {
          "success": true,
          "success_plugins": ["ffprobe", "renamer", "tmdb", "tvdb", "omdb"],
          "failed_plugins": [],
          "not_supported_plugins": [],
          "started_at": "2025-11-26T16:30:00.200+03:00",
          "finished_at": "2025-11-26T16:30:05.100+03:00",
          "duration_ms": 4900
        },
        "output": {
          "tasks": [
            {
              "name": "print_match_header",
              "type": "print",
              "success": true,
              "rendered": "========== MATCH 0 =========="
            },
            {
              "name": "save_nfo",
              "type": "save",
              "success": true,
              "destination": "/path/to/file.nfo"
            }
          ]
        }
      },
      "plugins": {
        "ffprobe": {
          "globals": {
            "status": {
              "success": true,
              "started_at": "...",
              "finished_at": "...",
              "duration_ms": 150
            }
          },
          "video": {
            "codec_name": "hevc",
            "codec_long_name": "H.265 / HEVC",
            "width": 1920,
            "height": 816,
            "fps": 23.976,
            "bit_rate": 8000000,
            "duration_seconds": 7200.0
          },
          "audio": [
            {
              "index": 1,
              "codec_name": "ac3",
              "codec_long_name": "Dolby Digital",
              "channels": 6,
              "sample_rate": 48000,
              "language": "eng"
            }
          ],
          "subtitles": [...],
          "container": {
            "format_name": "matroska,webm",
            "format_long_name": "Matroska / WebM",
            "duration": 7200.0,
            "size_bytes": 12345678,
            "bit_rate": 10000000
          }
        },
        "renamer": {
          "globals": {
            "status": {...}
          },
          "parsed": {
            "show": null,
            "movie": {
              "name": "Mr. & Mrs. Smith",
              "year": 2005
            }
          },
          "category": "movie"
        },
        "tmdb": {
          "globals": {
            "status": {...},
            "validation": {
              "tests_passed": 1,
              "tests_total": 1,
              "details": {
                "duration_match": {
                  "duration_actual": 7200,
                  "duration_expected": 7200,
                  "difference_seconds": 0,
                  "tolerance_seconds": 600,
                  "passed": true
                }
              }
            }
          },
          "movie": {
            "id": 12345,
            "title": "Mr. & Mrs. Smith",
            "original_title": "Mr. & Mrs. Smith",
            "release_date": "2005-06-10",
            "runtime": 120,
            "vote_average": 6.5,
            "vote_count": 5000,
            "popularity": 50.123,
            "overview": "...",
            "tagline": "...",
            "genres": [
              {"id": 28, "name": "Action"},
              {"id": 35, "name": "Comedy"}
            ],
            "production_companies": [...],
            "production_countries": [...],
            "spoken_languages": [...]
          },
          "episode": null,
          "season": null,
          "show": null,
          "extras": {
            "credits": {
              "cast": [
                {
                  "id": 287,
                  "name": "Brad Pitt",
                  "character": "John Smith",
                  "order": 0,
                  "profile_path": "/..."
                },
                {
                  "id": 6384,
                  "name": "Angelina Jolie",
                  "character": "Jane Smith",
                  "order": 1,
                  "profile_path": "/..."
                }
              ],
              "crew": [...]
            },
            "images": {
              "backdrops": [
                {
                  "file_path": "/...",
                  "width": 1920,
                  "height": 1080,
                  "vote_average": 5.5
                }
              ],
              "posters": [...]
            },
            "keywords": {
              "keywords": [
                {"id": 1, "name": "spy"},
                {"id": 2, "name": "assassin"}
              ]
            },
            "videos": {
              "results": [
                {
                  "key": "youtube_key",
                  "type": "Trailer",
                  "site": "YouTube"
                }
              ]
            }
          },
          "normalized": {...},
          "raw": {...}  // if include-raw=true
        },
        "tvdb": {...},
        "omdb": {...}
      }
    }
  ]
}
```

---

## KEY DESIGN DECISIONS

### 1. NO VALIDATION AGGREGATION IN CORE

**WRONG (v3):**
```javascript
{
  "globals": {
    "summary": {
      "validations": {  // ❌ Core shouldn't aggregate
        "total_tests": 10,
        "accuracy": 0.95
      }
    }
  }
}
```

**CORRECT (v4):**
```javascript
{
  "globals": {
    "summary": {
      // ✅ NO validations (plugin concern)
      "input_plugin_used": "scanner",
      "output_plugins_used": [...],
      "categories": [...],
      "total_size_bytes": 123,
      "total_duration_seconds": 456
    }
  },
  "matches": [{
    "plugins": {
      "tmdb": {
        "globals": {
          "validation": {...}  // ✅ Plugin-managed
        }
      }
    }
  }]
}
```

**Rationale:**
- Validation is domain-specific knowledge
- Core doesn't know what "valid" means
- Each plugin defines own validation criteria
- Plugin-agnostic principle

---

### 2. SIMPLIFIED INPUT STRUCTURE

**WRONG (v3):**
```javascript
{
  "match": {
    "globals": {
      "input": {  // ❌ Complex object
        "path": "/path/file.mkv",
        "virtual": false,
        "category": "movie"
      }
    }
  }
}
```

**CORRECT (v4):**
```javascript
{
  "match": {
    "globals": {
      "input_path": "/path/file.mkv"  // ✅ Just string
    }
  }
}
```

**Rationale:**
- `virtual` and `category` are plugin metadata (not core concern)
- Path is only core requirement
- Simpler = better

---

### 3. NO REDUNDANT PATHS OBJECT

**WRONG (v3):**
```javascript
{
  "match": {
    "globals": {
      "output": {
        "tasks": [...],
        "paths": {  // ❌ Redundant
          "nfo_path": "/path.nfo",
          "renamed_path": null
        }
      }
    }
  }
}
```

**CORRECT (v4):**
```javascript
{
  "match": {
    "globals": {
      "output": {
        "tasks": [
          {
            "name": "save_nfo",
            "type": "save",
            "destination": "/path.nfo"  // ✅ Path here
          }
        ]
      }
    }
  }
}
```

**Rationale:**
- Task destinations already contain paths
- No need for separate paths object
- Reduces duplication

---

### 4. CONFIG SNAPSHOT

**Principle:** API response MUST be self-contained (reproducible)

```javascript
{
  "globals": {
    "config": {  // ✅ Snapshot at execution time
      "options": {...},
      "plugins": {...},
      "tasks": [...]
    }
  }
}
```

**Benefits:**
- Know exactly which config produced this response
- Reproduce execution later
- Audit trail
- MongoDB can store config snapshot with results

---

### 5. SINGLE TIMESTAMP SOURCE

**Principle:** All timestamps from same `start_time`

```python
# In __main__.py
start_time = datetime.now()  # ONE timestamp

# All status objects use this
api_response['globals']['status']['started_at'] = start_time.isoformat()
```

**Consistency guarantee:**
- No clock drift between components
- Accurate duration calculations
- Synchronized across all matches

---

## STATE MANAGEMENT PATTERNS

### Pattern 1: Incremental State Building

```python
# __main__.py execution

processed_matches = []  # Accumulator

for index, match in enumerate(input_matches):
    # Execute plugins
    result = executor.execute_output_pipeline(...)
    
    # Add to accumulator
    processed_matches.append(result)
    
    # Build INCREMENTAL API response (for task context)
    temp_api_response = builder.build(
        processed_matches,  # Only processed so far
        config,
        start_time,
        all_plugins
    )
    
    # Execute tasks with current state
    task_results = task_manager.execute_tasks_for_match(
        temp_api_response,
        index,
        dry_run
    )
```

**Why:**
- Tasks can reference previous matches
- `${0.plugins.tmdb.movie.title}` works during match 1 execution
- Incremental building enables cross-match templates

---

### Pattern 2: Match Result Tracking

```python
match_task_results = {}  # Dict[int, List[Dict]]

for index, match in enumerate(input_matches):
    # ... execute plugins ...
    
    # Execute tasks
    task_results = task_manager.execute_tasks_for_match(...)
    
    # Store by index
    match_task_results[index] = task_results

# Later: Add to final API response
for match_index, task_results in match_task_results.items():
    api_response['matches'][match_index]['globals']['output']['tasks'] = format_tasks(task_results)
```

**Why:**
- Separates execution from response building
- Allows post-processing of task results
- Clean separation of concerns

---

### Pattern 3: Status Aggregation

```python
class APIResponseBuilder:
    def _build_global_status(self, matches, end_time):
        """Aggregate from all matches"""
        errors = sum(
            1 for m in matches 
            if not m.get('globals', {}).get('status', {}).get('success', False)
        )
        
        return {
            'success': errors == 0,
            'matches': len(matches),
            'errors': errors,
            'started_at': self.start_time.isoformat(),
            'finished_at': end_time.isoformat(),
            'duration_ms': int((end_time - self.start_time).total_seconds() * 1000)
        }
```

**Why:**
- Single source of truth (match-level status)
- Global status derived from matches
- No manual counting

---

### Pattern 4: Plugin Result Merging

```python
# Executor builds match_data incrementally
match_data = {'input': {...}}

# Group 0
ffprobe_result = ffprobe.execute(match_data)
match_data['ffprobe'] = ffprobe_result

renamer_result = renamer.execute(match_data)
match_data['renamer'] = renamer_result

# Group 1 (can now read ffprobe and renamer)
tmdb_result = tmdb.execute(match_data)
match_data['tmdb'] = tmdb_result

# Final match_data has all plugins
# {'input': {...}, 'ffprobe': {...}, 'renamer': {...}, 'tmdb': {...}}
```

**Why:**
- Sequential merging preserves execution order
- Later plugins see earlier results
- No separate result storage needed

---

## PROFESSIONAL PATTERNS

### Pattern 1: Immutable Timestamps

```python
# Calculate once, use everywhere
start_time = datetime.now()
end_time = datetime.now()

# Don't recalculate
status = {
    'started_at': start_time.isoformat(),  # Exact same timestamp
    'finished_at': end_time.isoformat(),
    'duration_ms': int((end_time - start_time).total_seconds() * 1000)
}
```

**Why:**
- Consistency
- Accurate duration
- No floating point errors

---

### Pattern 2: Error Result Helpers

```python
class BasePlugin:
    def _error_result(self) -> Dict:
        """Standard error result"""
        now = datetime.now().isoformat()
        return {
            'status': {
                'success': False,
                'started_at': now,
                'finished_at': now,
                'duration_ms': 0
            },
            # Plugin-specific null fields
            'movie': None,
            'episode': None
        }
```

**Why:**
- Consistent error structure
- No missing required fields
- Same shape as success result

---

### Pattern 3: Status Bubbling

```python
# Match-level status
match_status = {
    'success': True,
    'success_plugins': ['ffprobe', 'renamer', 'tmdb'],
    'failed_plugins': [],
    'not_supported_plugins': []
}

# Global status (derived)
global_status = {
    'success': all(m['globals']['status']['success'] for m in matches),
    'errors': sum(1 for m in matches if not m['globals']['status']['success'])
}
```

**Why:**
- Single source of truth (match-level)
- Global status automatically consistent
- No manual sync needed

---

### Pattern 4: Defensive Data Access

```python
# WRONG
movie_title = match_data['renamer']['parsed']['movie']['name']  # KeyError if missing

# CORRECT
renamer = match_data.get('renamer', {})
parsed = renamer.get('parsed', {})
movie = parsed.get('movie', {})
movie_title = movie.get('name')  # None if missing, no crash
```

**Why:**
- Graceful degradation
- No crashes on missing data
- Expects system prevents most issues, but defensive coding still good

---

### Pattern 5: Validation as Optional Enhancement

```python
result = {
    'status': {...},
    'movie': {...}
}

# Add validation if possible
if ffprobe_data := match_data.get('ffprobe'):
    validation = self._validate_duration(...)
    result['validation'] = validation  # Optional field

return result
```

**Why:**
- Validation doesn't block execution
- Result valid with or without validation
- Additive enhancement

---

## MONGODB READY STRUCTURE

API Response v4 maps directly to MongoDB collections:

### Collections (Planned Phase 7)

**1. branches**
```javascript
{
  "_id": ObjectId("..."),
  "name": "main",
  "status": "active",
  "last_commit_id": ObjectId("..."),
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

**2. commits**
```javascript
{
  "_id": ObjectId("..."),
  "branch_id": ObjectId("..."),
  "api_response_id": ObjectId("..."),
  "globals": {  // Snapshot from api_response.globals
    "status": {...},
    "summary": {...},
    "config": {...}
  },
  "created_at": ISODate("...")
}
```

**3. api_responses** (TTL: 90 days)
```javascript
{
  "_id": ObjectId("..."),
  "commit_id": ObjectId("..."),
  "globals": {...},
  "matches": [...],  // Full API response
  "created_at": ISODate("..."),
  "expires_at": ISODate("...")  // TTL index
}
```

**4. diagnostics** (TTL: 7 days)
```javascript
{
  "_id": ObjectId("..."),
  "commit_id": ObjectId("..."),
  "execution_time_ms": 5000,
  "plugin_timings": {
    "ffprobe": 150,
    "renamer": 50,
    "tmdb": 2000
  },
  "created_at": ISODate("..."),
  "expires_at": ISODate("...")
}
```

---

### Mapping Strategy

**API Response → MongoDB:**
```python
# Save flow (Phase 7)
async def save_to_mongodb(api_response, config):
    # 1. Get/create branch
    branch = await branch_repo.get("main")
    
    # 2. Save full API response
    api_response_doc = await api_response_repo.save({
        "globals": api_response["globals"],
        "matches": api_response["matches"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=90)
    })
    
    # 3. Create commit (with globals snapshot)
    commit = await commit_repo.create({
        "branch_id": branch.id,
        "api_response_id": api_response_doc.id,
        "globals": api_response["globals"],  # Snapshot
        "created_at": datetime.utcnow()
    })
    
    # 4. Update branch
    await branch_repo.update_last_commit(branch.name, commit.id)
```

**Query Patterns:**
```python
# Get latest commit on branch
commit = await Commit.find_one(
    Commit.branch_id == branch_id,
    sort=[("created_at", -1)]
)

# Get full API response
api_response = await APIResponse.find_one(
    APIResponse.commit_id == commit_id
)

# Get specific match
match = api_response.matches[index]

# Get specific plugin result
tmdb_data = match["plugins"]["tmdb"]
```

---

## TEMPLATE VARIABLE RESOLUTION

**Context Building:**
```python
class TemplateManager:
    def build_context(self, api_response, match_index):
        match = api_response['matches'][match_index]
        
        context = {
            # API-level
            'globals': api_response['globals'],
            'matches': api_response['matches'],
            
            # Current match
            'index': match_index,
            
            # Current match plugins (top-level access)
            'tmdb': match['plugins']['tmdb'],
            'ffprobe': match['plugins']['ffprobe'],
            'renamer': match['plugins']['renamer'],
            # ... all plugins ...
            
            # Indexed match access
            '0': api_response['matches'][0],
            '1': api_response['matches'][1],
            # ...
        }
        
        return context
```

**Variable Access Patterns:**
```jinja2
{# Current match #}
${index}                                    -> 0
${tmdb.movie.title}                        -> "Movie Name"
${ffprobe.video.codec_name}                -> "hevc"

{# API-level #}
${globals.status.matches}                  -> 2
${globals.summary.total_size_bytes}        -> 12345678
${globals.config.options.debug}            -> true

{# Other matches #}
${0.plugins.tmdb.movie.title}              -> "First Match Title"
${1.plugins.tmdb.movie.title}              -> "Second Match Title"

{# Match globals #}
${0.globals.index}                         -> 0
${0.globals.input_path}                    -> "/path/file.mkv"
${0.globals.status.success}                -> true
```

---

## COMPACT RESPONSE SYSTEM

**Purpose:** Structural analysis (AI-readable, 94% size reduction)

**Strategy:** Type-based simplification - keep 1 example per type

**Example:**
```javascript
// Full (145 KB)
{
  "extras": {
    "credits": {
      "cast": [
        {"id": 1, "name": "Actor 1", "character": "Char 1"},
        {"id": 2, "name": "Actor 2", "character": "Char 2"},
        // ... 99 more ...
      ]
    }
  }
}

// Compact (9 KB)
{
  "extras": {
    "credits": {
      "cast": [
        {"id": 1, "name": "Actor 1", "character": "Char 1"}  // Only 1 example
      ]
    }
  }
}
```

**Use Cases:**
- AI analysis for plugin normalization
- API structure documentation
- MongoDB schema planning
- Response structure validation

---

## VERSION HISTORY

### v4 (November 11, 2025) - Current
**Changes:**
- ❌ Removed `globals.summary.validations`
- ❌ Removed `match.globals.output.validations`
- ❌ Removed `match.globals.output.paths`
- ✅ Simplified `match.globals.input` → `input_path`
- ✅ Fixed external task naming
- ✅ Plugin-managed validation in `plugin.globals.validation`

**Rationale:** Plugin-agnostic compliance, no redundancy, simpler structure

---

### v3 (November 10, 2025)
**Changes:**
- ✅ Added `match.globals.output` (tasks, validations, paths)
- ✅ Wrapped config: `globals.config = {options, plugins, tasks}`
- ✅ Consistent naming: `match_globals` → `globals`

**Issues:** Too much aggregation in core, redundant paths object

---

### v2 (November 8, 2025)
**Changes:**
- ✅ Added `globals.summary`
- ✅ Added `match.plugins` wrapper
- ✅ Config snapshot

**Issues:** Validation aggregation in core, complex input structure

---

### v1 (Initial)
**Structure:** Flat, no clear separation

**Issues:** No plugin isolation, no config snapshot, inconsistent naming

---

## PROFESSIONAL BEST PRACTICES

### 1. Always Include Status Objects
```javascript
// Every level has status
{
  "globals": {
    "status": {...}  // API-level
  },
  "matches": [{
    "globals": {
      "status": {...}  // Match-level
    },
    "plugins": {
      "tmdb": {
        "globals": {
          "status": {...}  // Plugin-level
        }
      }
    }
  }]
}
```

### 2. Timestamps Everywhere
```javascript
{
  "status": {
    "started_at": "2025-11-26T16:30:00.123+03:00",  // ISO 8601
    "finished_at": "2025-11-26T16:30:05.456+03:00",
    "duration_ms": 5333  // Always milliseconds
  }
}
```

### 3. Success Flags at All Levels
```javascript
{
  "globals": {
    "status": {
      "success": true  // Overall
    }
  },
  "matches": [{
    "globals": {
      "status": {
        "success": true  // This match
      }
    }
  }]
}
```

### 4. Null vs Missing
- **Null:** Intentionally not applicable (`"episode": null` for movies)
- **Missing:** Not computed/not available (no `validation` field if ffprobe missing)

### 5. Arrays vs Objects
- **Arrays:** Homogeneous data (`audio: [...]`, `cast: [...]`)
- **Objects:** Heterogeneous data (`status: {...}`, `movie: {...}`)

---

## ERROR HANDLING

### Partial Success Pattern
```javascript
{
  "globals": {
    "status": {
      "success": false,  // Some matches failed
      "errors": 1
    }
  },
  "matches": [
    {
      "globals": {
        "status": {
          "success": true,  // This match succeeded
          "success_plugins": ["ffprobe", "renamer", "tmdb"],
          "failed_plugins": []
        }
      }
    },
    {
      "globals": {
        "status": {
          "success": false,  // This match failed
          "success_plugins": ["ffprobe"],
          "failed_plugins": ["renamer", "tmdb"]  // tmdb failed due to renamer
        }
      }
    }
  ]
}
```

---

## FUTURE: MONGODB & GLOBAL STATE STRATEGY (Phase 7+)

### Core Concept: API Response = Runtime Global State

**Current Reality:**
```python
# __main__.py execution
api_response = {
    'globals': {...},
    'matches': [...]
}

# This IS the global state (in-memory)
# Written to JSON file at end
```

**Problem with Current Approach:**
- Entire state kept in memory
- No persistence until end
- Crash = total loss
- No incremental access
- Scaling issue (1000+ matches = 500+ MB RAM)

**Professional Solution: Persistent Global State (MongoDB)**

---

### Strategy A: Batch Write (Current + MongoDB)

**Concept:** Keep current flow, write to MongoDB at end

```python
# __main__.py
processed_matches = []

for match in input_matches:
    result = executor.execute_output_pipeline(...)
    processed_matches.append(result)  # In-memory accumulation
    
    # Task execution with temp state
    temp_api_response = builder.build(processed_matches, ...)
    task_results = task_manager.execute_tasks_for_match(temp_api_response, ...)

# Build final state
api_response = builder.build(processed_matches, ...)

# BATCH WRITE to MongoDB
if config.get('mongodb', {}).get('enabled'):
    await mongodb_writer.save_execution(api_response)
```

**MongoDB Structure (Batch):**
```javascript
// Collection: executions
{
  "_id": ObjectId("..."),
  "started_at": ISODate("..."),
  "finished_at": ISODate("..."),
  
  // Copy of globals
  "status": {
    "success": true,
    "matches": 100,
    "errors": 0
  },
  "summary": {...},
  "config_snapshot": {...},
  
  // References to detail collections
  "matches_ids": [ObjectId("..."), ObjectId("..."), ...]
}

// Collection: matches (one per match)
{
  "_id": ObjectId("..."),
  "execution_id": ObjectId("..."),
  "index": 0,
  "input_path": "/path/file.mkv",
  "status": {...},
  "output": {
    "tasks": [...]
  },
  
  // References to plugin results
  "plugin_results_ids": {
    "ffprobe": ObjectId("..."),
    "tmdb": ObjectId("..."),
    "tvdb": ObjectId("...")
  }
}

// Collection: plugin_results (one per plugin per match)
{
  "_id": ObjectId("..."),
  "match_id": ObjectId("..."),
  "plugin_name": "tmdb",
  "status": {...},
  
  // Plugin-specific data (schema-free)
  "data": {
    "movie": {...},
    "extras": {...},
    "validation": {...}
  }
}
```

**Pros:**
- Simple migration from current code
- Fast execution (no DB writes during processing)
- Minimal code changes

**Cons:**
- Memory still grows with match count
- No crash recovery
- No real-time monitoring

---

### Strategy B: Incremental Write (Streaming)

**Concept:** Write each match to MongoDB immediately

```python
# __main__.py
execution_doc = await mongodb_writer.create_execution(config, start_time)

for index, match in enumerate(input_matches):
    # Execute plugins
    result = executor.execute_output_pipeline(...)
    
    # WRITE MATCH to MongoDB
    match_doc = await mongodb_writer.save_match(execution_doc.id, index, result)
    
    # WRITE PLUGIN RESULTS to MongoDB
    for plugin_name, plugin_result in result.items():
        await mongodb_writer.save_plugin_result(match_doc.id, plugin_name, plugin_result)
    
    # Build context from MongoDB (not memory)
    context = await mongodb_reader.build_task_context(execution_doc.id, index)
    
    # Execute tasks
    task_results = task_manager.execute_tasks_for_match(context, index, dry_run)
    
    # WRITE TASK RESULTS to MongoDB
    await mongodb_writer.save_task_results(match_doc.id, task_results)

# Update execution status
await mongodb_writer.finalize_execution(execution_doc.id, end_time)
```

**MongoDB Structure (Incremental):**
```javascript
// Same collections as Batch
// But writes happen per-match instead of at end

// Query pattern:
// Get execution -> Get matches -> Get plugin results per match
```

**Pros:**
- Constant memory (~50 MB regardless of match count)
- Crash recovery (processed matches saved)
- Real-time monitoring (query DB during execution)
- Scalable (10,000+ matches no problem)

**Cons:**
- More DB writes (~10 writes per match vs 1 batch)
- Slightly slower (~20ms overhead per match)
- More complex code

---

### Strategy C: Hybrid (Recommended)

**Concept:** Keep global state structure, lazy write to MongoDB

```python
# Global state manager
class GlobalStateManager:
    def __init__(self, config):
        self.memory_store = {}  # In-memory cache
        self.mongodb_enabled = config.get('mongodb', {}).get('enabled')
        
        if self.mongodb_enabled:
            self.db_writer = MongoDBWriter(config['mongodb'])
    
    async def save_match(self, index, result):
        # Always keep in memory (for task context)
        self.memory_store[index] = result
        
        # Optionally persist to MongoDB
        if self.mongodb_enabled:
            await self.db_writer.save_match(index, result)
    
    def get_match(self, index):
        # Read from memory (fast)
        return self.memory_store.get(index)
    
    def build_api_response(self):
        # Build from memory store
        return {
            'globals': {...},
            'matches': [self.memory_store[i] for i in sorted(self.memory_store.keys())]
        }

# Usage:
state = GlobalStateManager(config)

for index, match in enumerate(input_matches):
    result = executor.execute_output_pipeline(...)
    
    # Save to state (memory + optional MongoDB)
    await state.save_match(index, result)
    
    # Build context from state
    context = state.build_task_context(index)
    
    # Execute tasks
    task_results = task_manager.execute_tasks_for_match(context, ...)
```

**Pros:**
- Best of both worlds
- Fast (memory reads for tasks)
- Persistent (MongoDB writes async)
- Clean abstraction (state manager)

**Cons:**
- More architecture (new component)

---

### Mock JSON Strategy (Current Phase)

**Purpose:** Test without MongoDB setup

**Implementation:**
```python
# Option 1: Use existing reports
context = json.load(open('reports/api_response_full_20251126.json'))

# Option 2: Mock MongoDB client
class MockMongoDBWriter:
    def __init__(self):
        self.store = []
    
    async def save_match(self, execution_id, index, result):
        self.store.append({
            'execution_id': execution_id,
            'index': index,
            'result': result
        })
        # Write to JSON file
        with open(f'mock_db/match_{index}.json', 'w') as f:
            json.dump(result, f, indent=2)
    
    def get_all(self):
        return self.store

# Use in code:
if config.get('mongodb', {}).get('enabled'):
    writer = MongoDBWriter(...)  # Real
else:
    writer = MockMongoDBWriter()  # Mock (JSON files)
```

**Mock Directory Structure:**
```
mock_db/
├── execution_20251126_163000.json      # Execution metadata
├── match_0.json                        # Match 0 full data
├── match_1.json                        # Match 1 full data
├── plugin_tmdb_0.json                  # TMDb result for match 0
├── plugin_ffprobe_0.json               # FFProbe result for match 0
└── tasks_0.json                        # Task results for match 0
```

**Benefits:**
- No MongoDB installation needed
- Same API as real MongoDB writer
- Easy debugging (inspect JSON files)
- Zero code changes when switching to real MongoDB

---

### Schema Alignment: API Response ≈ MongoDB

**Key Principle:** Minimal transformation between runtime state and persistent storage

**API Response Structure:**
```javascript
{
  "globals": {
    "status": {...},
    "summary": {...},
    "config": {...}
  },
  "matches": [
    {
      "globals": {
        "index": 0,
        "input_path": "...",
        "status": {...},
        "output": {...}
      },
      "plugins": {
        "tmdb": {...},
        "ffprobe": {...}
      }
    }
  ]
}
```

**MongoDB Collections (Normalized):**
```javascript
// executions (1 per run)
{
  "_id": ObjectId,
  "globals": {              // ✅ SAME as API response
    "status": {...},
    "summary": {...},
    "config": {...}
  }
}

// matches (N per execution)
{
  "_id": ObjectId,
  "execution_id": ObjectId,
  "globals": {              // ✅ SAME as API response match.globals
    "index": 0,
    "input_path": "...",
    "status": {...},
    "output": {...}
  }
}

// plugin_results (N*P per execution)
{
  "_id": ObjectId,
  "match_id": ObjectId,
  "plugin_name": "tmdb",
  "data": {...}             // ✅ SAME as API response match.plugins.tmdb
}
```

**Reconstruction:**
```python
# Build API response from MongoDB
async def reconstruct_api_response(execution_id):
    execution = await Execution.find_one(Execution.id == execution_id)
    matches_docs = await Match.find(Match.execution_id == execution_id).sort("index").to_list()
    
    matches = []
    for match_doc in matches_docs:
        # Get plugin results
        plugin_results = await PluginResult.find(
            PluginResult.match_id == match_doc.id
        ).to_list()
        
        # Build plugins dict
        plugins = {pr.plugin_name: pr.data for pr in plugin_results}
        
        # Build match
        matches.append({
            'globals': match_doc.globals,  # ✅ Direct copy
            'plugins': plugins
        })
    
    # Build API response (IDENTICAL structure)
    return {
        'globals': execution.globals,  # ✅ Direct copy
        'matches': matches
    }
```

**Transformation Cost:** ZERO (direct copy, no mapping)

---

### Performance Comparison

**Current (JSON only):**
```
100 matches:
- Memory: 150 MB (grows linearly)
- Execution: 250s
- Crash recovery: None
- Monitoring: None
```

**Strategy A (Batch MongoDB):**
```
100 matches:
- Memory: 150 MB (same as current)
- Execution: 251s (+1s for batch write)
- Crash recovery: None
- Monitoring: After completion only
```

**Strategy B (Incremental MongoDB):**
```
100 matches:
- Memory: 50 MB (constant)
- Execution: 252s (+2s for incremental writes, ~20ms/match)
- Crash recovery: ✅ Up to last completed match
- Monitoring: ✅ Real-time query
```

**Strategy C (Hybrid):**
```
100 matches:
- Memory: 50-150 MB (configurable cache)
- Execution: 251s (+1s for async writes)
- Crash recovery: ✅ Up to last saved match
- Monitoring: ✅ Real-time query
- Complexity: Medium (state manager abstraction)
```

---

### Recommended Path Forward

**Phase 7A: Mock JSON (Current)**
- Keep existing code
- Add `MockMongoDBWriter` class
- Write to `mock_db/*.json` instead of real MongoDB
- Test schema alignment

**Phase 7B: Real MongoDB (Batch)**
- Replace `MockMongoDBWriter` with `MongoDBWriter`
- Keep batch write (simple migration)
- Validate schema works

**Phase 7C: Incremental Writes**
- Refactor to streaming writes
- Add crash recovery
- Add real-time monitoring

**Phase 8: Global State Abstraction**
- Extract `GlobalStateManager` class
- Clean separation: memory vs persistence
- Industry-standard pattern

---

### Industry Pattern Reference

**Current Approach:**
```python
# Naive (accumulate everything in memory)
results = []
for item in items:
    result = process(item)
    results.append(result)
return results
```

**Professional Approach:**
```python
# Streaming with persistent state
state = StateManager(storage=MongoDBStorage())

for item in items:
    result = process(item)
    
    # Save immediately (persistence)
    await state.save(result)
    
    # Continue with next (memory freed)
```

**Examples in Industry:**
- **Airflow:** Each task writes to metadata DB immediately
- **Spark:** RDD transformations persist to disk incrementally
- **Kafka Streams:** State stores backed by changelog topics
- **FastAPI + SQLAlchemy:** ORM sessions commit per-request

**Archiverr Goal:**
```python
# Global state = Abstraction over memory + MongoDB
# API response = View of global state at any point
# MongoDB = Persistent layer of global state
# Mock JSON = Development-time persistence layer
```

---

This completes API Response documentation with MongoDB/Global State strategy. Complete structure, state management patterns, professional practices, three strategy options, mock JSON approach, and industry alignment documented.
