# Progress

**Last Updated:** August 15, 2026

Bu dosya ayrıntılı oturum günlüğü değil, kısa durum özeti içindir.

## Stable Milestones

- Plugin-agnostic core kuralı yerleşik ve korunuyor.
- Manifest-driven plugin mimarisi aktif kullanımda.
- Aktif 9 plugin modern sözleşme üzerinde çalışıyor.
- MongoDB zorunlu değil; CLI/API tarafı degrade/off senaryolarıyla çalışabiliyor.
- FastAPI ana akış entegrasyonu E2E kanıtlandı: Mongo up/down/full-mode senaryoları doğrulandı.
- API responses artık Mongo persistence durumunu açıkça gösteriyor.
- Event contract daraltıldı: pluginler için okuma tarafı açık, yazma tarafı bilinçli olarak kapalı.
- Data Resolver Namespace aktif: `data.<jobindex>.<category>.<dotted.path>`.
- Jinja2 render engine core'a taşındı; tasker render motoru değil, print/save dispatcher.
- `RunState.data` Mongo'da `runs.data` olarak persist ediliyor.

## Current Focus

- Session 40 A–F landed (state API, jobid interpolator, output aggregate, TVMaze flat)
- CI workflow + optional TMDb smoke
- Later: S41 stub delete, web, new plugins, match quality

## Session 39 Milestone

- R15 planı tamamlandı: Data Resolver Namespace + Render Refactor.
- 23 commit across 7 phases: A=3, C=2, H=5, I=1, B=1, C5=1, D=5, E=2, F=2, G=1.
- Test baseline: 687 passed / 13 skipped / 0 fails (post-G1).
- Plugin-agnostic guard: 9/9 PASS; core'a yeni plugin-name leak girmedi.
- Real E2E verified: Breaking Bad fixture flat TMDb shape ile render edildi ve `run.data` Mongo'da persist edildi.
- G1 real E2E, unit testlerin yakalamadığı Mongo bug'ını buldu: integer job-index keys `Invalid document: documents must have only string keys` hatası; `RunState.to_dict()` boundary'sinde `_stringify_int_keys` ile düzeltildi.
- Synthetic `plugin.<name>.{data,status}` template namespace kaldırıldı; yeni template yüzeyi `jobs[job_id].plugins.<name>`, `job.plugins.<name>`, `data.*`, `run.*`.
- TMDb shape standardize edildi: sadece `show` + `movie` ana key'leri; episode/season bilgisi `show` içine flat işlendi.
- OMDb / TVMaze / TVDB current non-flat shape ile `emits` deklare ediyor; convention alignment sonraki sprint'e bırakıldı.
- Mid-sprint audit commit 18 sonrası APPROVED 10/10; final audit API overload nedeniyle tamamlanamadı, manual sanity verification kullanıldı.

## Session 37 Milestone

- MongoDB + FastAPI end-to-end sprint tamamlandı.
- 9 commit: PASS 1-5, PASS 6 smoke bug fix, PASS 7-8, HANDOFF update.
- Unit suite: 514 passed / 12 skipped; ZERO TOLERANCE plugin-agnostic guard: 14/14 PASS.
- E2E verified: Mongo UP persisted=true, Mongo DOWN degraded persisted=false, Mongo DOWN full-mode 503.
- `GET /runs/{id}/jobs` ObjectId 500 bug fixed during smoke.
- Diagnostics surface and duplicate async Mongo globals archived under `.deleted/`.

## Still Pending

- OMDb / TVMaze / TVDB flat-shape migration decision or explicit divergence documentation
- S39 resolver-envelope smells: private `_jobs` access, resolver caching, sub-path enumeration work
- Untracked artifact disposition: `AI/`, `ONEMLI/`, `user-prompts/`, `datasets/15-runtime-state-example.json`
- CI/CD kurulumu
- Bazı iç veri tekrarlarının sadeleştirilmesi
- RunRepository stub cleanup
- Per-run plugin_executions schema/wiring decision
- Legacy Mongo collection backup/drop
- Real TMDb smoke test
- Pydantic dead schema cleanup
- `/run/` long-term deprecation decision

## Historical Detail

Detaylı oturum geçmişi için `memory-bank/sessions/` klasörü yalnızca gerektiğinde okunmalıdır.
