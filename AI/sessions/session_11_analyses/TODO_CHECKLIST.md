# SESSION 11 - TODO CHECKLIST

```yaml
tarih: 2025-12-04
format: Sadece başlıklar - kod detayı yok
```

---

## ✅ TAMAMLANAN

- [x] 4-Stage Pipeline (INPUT → PARSE → DATA → OUTPUT)
- [x] Plugin Registry & Stage Assignment
- [x] Parallel Execution (DATA stage)
- [x] Debug System
- [x] Event Bus
- [x] FlexGet-Style Config
- [x] User Aliases (m, p, s, video)
- [x] Jinja2 Template Rendering
- [x] Mock Persistence Backend

---

## 🔴 P0 - KRİTİK

- [ ] `config` alias template context'e inject
- [ ] `!include` directive test et
- [ ] External task sistemini kaldır → config imports

---

## 🟡 P1 - YÜKSEK

- [ ] state.update non-lockable olmalı (conflict fix)
- [ ] Lockable provides path-based locking
- [ ] requires: provides.X satisfaction tracking
- [ ] trigger_rule: one_success implement

---

## 🟢 P2 - NORMAL

- [ ] System aliases: provides, events
- [ ] complete_provide() plugin API
- [ ] trigger_rule: all_fail, none_fail
- [ ] Manifest içinde Jinja2 kullanımı
- [ ] reactive: true plugin handling

---

## ⚪ P3 - DÜŞÜK

- [ ] Memory management (hot/cold tiering)
- [ ] PyMongo real backend test
- [ ] Lazy loading for plugin data

---

## NOTLAR

1. **Test Komutu:**
   ```bash
   PYTHONPATH=src ARCHIVERR_DB_BACKEND=mock python -m archiverr
   ```

2. **Çalışan Çıktı:**
   - 4 stage tamamlanır
   - Tasker print output görünür
   - Exit code: 0

3. **Bilinen Uyarılar:**
   - W003: Hardcoded API keys
   - E016: state.update conflict (non-lockable olmalı)

---

**Son Güncelleme:** 2025-12-04
