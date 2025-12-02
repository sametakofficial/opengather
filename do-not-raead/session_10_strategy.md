# SESSION 10 STRATEGY

```yaml
date: 2025-11-28
type: strategy
status: ready_for_execution
previous_session: 9
focus: Session 9 Cleanup & Tests
```

---

## SCOPE

**Basit ve gerçekçi hedefler.** Over-engineering yok.

Archiverr = Basit CLI aracı. Dosya tara → metadata çek → işle → bitti.

---

## TASKS

### 1. TMDb PluginResult Kullanımı (15 dk)

**Problem:** TMDb hala `Dict[str, Any]` döndürüyor

**Fix:**
```python
# Önce (client.py line 73)
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:

# Sonra
def execute(self, match_data: Dict[str, Any]) -> PluginResult:
    ...
    return PluginResult.success_result(data={...})
```

### 2. emit_task() Örneği (10 dk)

**Problem:** emit_task() var ama hiç kullanılmıyor

**Fix:** TMDb'de basit bir örnek ekle:
```python
def execute(self, match_data):
    ...
    if result.get('movie'):
        self.emit_task({
            "type": "print",
            "template": "Found: {{ tmdb.movie.title }}"
        })
```

### 3. SDK Unit Tests (30 dk)

**Eksik:** SDK için hiç test yok

**Eklenecek testler:**
- `test_plugin_result.py` - PluginResult factory methods
- `test_base_plugin.py` - BasePlugin logging methods
- `test_manifest.py` - PluginManifest validation

---

## FILES TO MODIFY

| File | Change |
|------|--------|
| `plugins/tmdb/client.py` | Return PluginResult, add emit_task() example |
| `tests/unit/core/test_plugin_sdk.py` | SDK unit tests |

---

## SUCCESS CRITERIA

1. ✅ TMDb `PluginResult` döndürüyor
2. ✅ emit_task() çalışan örneği var
3. ✅ SDK testleri geçiyor
4. ✅ `python -m archiverr` hatasız çalışıyor

---

## NOT DOING

- ❌ DataEnvelope pattern (gereksiz)
- ❌ ExecutionStore/XCom (gereksiz)
- ❌ Hook System (gereksiz)
- ❌ Streaming/Generator (gereksiz)

**KISS - Keep It Simple, Stupid!**
