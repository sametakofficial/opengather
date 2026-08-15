# Archiverr Plugin Conventions

> **Status:** Conventions, NOT contracts.
> **Scope:** the soft rules that make plugins play nicely together
> in the data namespace + render context. None of this is enforced
> by the core; a plugin that ignores the conventions still loads
> and runs, but it won't participate in the resolver namespace and
> may surprise other plugins reading its output.

---

## Why conventions exist

The core is plugin-agnostic — `core/*` may not contain plugin name
literals, must not branch on plugin identity, and treats every
plugin as an opaque dispatcher. That means anything that needs to
COOPERATE between plugins (TMDb's title vs. OMDb's title; tasker
reading both) lives in convention, not code.

This document captures the conventions that lock in via:

- `manifest.emits` declarations (Phase A — declares what a plugin
  writes via `update_plugin(data=...)`);
- the `data.<jobindex>.<category>.<dotted.path>` resolver namespace
  (Phase D — `state/data_resolver.py`);
- the `data_priority` config (Phase D — `config.yml` + dataset
  `01-config.yml`).

When a plugin follows the conventions, an operator can swap providers
behind a single config key. When a plugin doesn't, the operator can
still address it directly via `jobs[job_id].plugins.<name>.<field>`
— it just won't be reachable via `data.*`.

---

## Reference shape: TMDb (Phase B aligned)

TMDb is the convention reference (S39 §B1+B2). Every metadata plugin
that wants to cooperate should converge toward this shape. Until a
plugin migrates, it can declare its CURRENT shape in `emits`; the
resolver consumes whatever's declared.

### Top-level result keys (returned by `update_plugin(data=...)`)

```yaml
data:
  show: { ... flat dict ... }     # TV media
  movie: { ... flat dict ... }    # film media
```

That's it. NO `episode`, NO `season`, NO `validation`, NO
`media_type`. Episode and season information is BAKED FLAT into the
`show` dict.

### `show` shape

```yaml
show:
  identifiers:
    tmdb_id: "1396"
    imdb_id: "tt0903747"
  title:
    primary: "Breaking Bad"
    original: "Breaking Bad"
    localized: "Breaking Bad"
  air_dates:
    first: "2008-01-20"
    last: "2013-09-29"
    year: 2008
  status: "Ended"
  runtime: 47
  ratings:
    tmdb:
      score: 8.9
      votes: 11000
  overview: "..."
  genres: ["Drama", "Crime"]
  network:
    name: "AMC"
    id: "174"
  seasons:
    total: 5
  episodes:
    total: 62

  # When an episode lookup happened, episode info is FLAT here:
  season_number: 1
  episode_number: 1
  episode_title: "Pilot"
  episode_overview: "..."
  episode_air_date: "2008-01-20"
  episode_runtime: 58

  # When a season lookup happened, season info is FLAT here:
  season_name: "Season 1"
  season_overview: "..."
  season_air_date: "2008-01-20"
  season_episode_count: 7

  images:
    poster: "/path"
    backdrop: "/path"
    episode_still: "/path"     # only when episode lookup happened
    season_poster: "/path"     # only when season lookup happened

  people:
    cast: [{ id, name, character, order, profile_image }, ...]
    crew: [{ id, name, job, department, profile_image }, ...]

  # Episode-scoped extras, surfaced flat:
  episode_people:
    cast: [...]
    crew: [...]
    guest_stars: [...]

  videos: [{ id, key, name, site, type, size }, ...]
  keywords: ["...", ...]
```

### `movie` shape

```yaml
movie:
  identifiers:
    tmdb_id: "27205"
    imdb_id: "tt1375666"
  title: { primary, original, localized }
  release:
    date: "2010-07-16"
    year: 2010
    status: "Released"
  runtime: 148
  ratings: { tmdb: { score, votes } }
  overview: "..."
  genres: ["Action", "Sci-Fi"]
  financial: { budget: ..., revenue: ... }
  images: { poster, backdrop }
  people: { cast, crew }
  videos: [...]
  keywords: [...]
```

---

## Adding a new category

The data namespace is OPEN: categories are plugin-defined. To add
e.g. a `book` or `game` category:

1. Pick a category root noun (lowercase, snake_case if multi-word).
2. Declare it in your plugin's `manifest.emits`:
   ```yaml
   emits:
     book:
       - title.primary
       - identifiers.isbn
   ```
3. Add a `data_priority` entry referencing that root:
   ```yaml
   data_priority:
     "data.<jobindex>.book": [yourplugin]
   ```
4. Operators can then write `{{ data.<jobindex>.book.title.primary }}`.

You do NOT need to ask anyone permission. The resolver and
template walker treat the category as opaque.

---

## Opting out of the data namespace

Don't declare `manifest.emits`. The resolver simply skips your
plugin. Direct access (`jobs[job_id].plugins.<name>.<field>`) still
works — anything you write via `update_plugin(data=...)` is
reachable, just not via `data.*`.

This is the right choice for plugins that:
- write internal-only state nobody else consumes;
- don't follow the show/movie convention and don't want to;
- emit a unique shape that doesn't match priority semantics
  (e.g. ffprobe's container/streams blocks).

---

## When you DO declare emits

- List every dotted path you write under each category. Wildcards
  are NOT supported; the resolver iterates exactly the listed paths
  during `_recompute_data_envelope`.
- Don't declare paths you don't actually write. The runtime won't
  crash, but the envelope will store None misses (skipped) and
  operators reading the envelope will see gaps.
- It's fine to declare more paths than you populate in any given
  run; the convention is about what CAN appear, not what MUST.

---

## Cross-plugin reads (with services)

When you need to read another plugin's data:

```python
def execute(self, job, services):
    parsed = job.plugins.get('renamer', {}).get('parsed', {})
    # or, for cross-job reads:
    other_job = services.get_all_jobs()[index]
    other_data = other_job.plugins.get('tmdb', {})
```

Declare the dependency in your manifest:

```yaml
requires:
  - plugin.renamer.parsed:success
```

The parse-time `template_dependency_validator` (Phase I) WILL warn
if your plugin's config templates reference a plugin not in your
`requires`. The runtime won't fail, but operators see an explicit
mismatch surface at registry init.

---

## Template paradigm (S39 §C1+)

The synthetic `plugin.<name>.{data,status}` namespace was REMOVED
in S39 §C1. Use one of:

| Form                                                      | Use case                       |
|-----------------------------------------------------------|--------------------------------|
| `{{ job.plugins.<name>.<field> }}`                        | current-job shortcut           |
| `{{ jobs[job_id].plugins.<name>.<field> }}`               | full canonical descent         |
| `{{ data.<jobindex>.<category>.<path> }}`                 | resolver-priority lookup       |
| `{{ data.run.<category>.<path> }}`                        | per_run plugin resolver        |
| `{{ jobid }}` / `${jobid}`                                | orchestrator current job id    |

`<jobindex>` in priority keys is a sentinel substituted at lookup
time; in template paths you can use the literal sentinel
(`data.<jobindex>.show`) — the proxy substitutes the active job's
index.

---

## Cross-references

- `datasets/02-manifest.yml` — `emits` schema
- `datasets/01-config.yml` — `data_priority` schema + contract
- `datasets/04-template-context.yml` — render context shape
- `datasets/13-plugin-system-overview.yml` — full system map
- `state/data_resolver.py` — resolver implementation
- `core/render/template_dependency_validator.py` — parse-time WARN

---

## Summary

> If your plugin declares `manifest.emits` and the operator lists
> it in `data_priority`, your output is interchangeable with any
> other plugin emitting the same paths. If you opt out, you remain
> a first-class citizen via direct descent. The conventions buy
> interchangeability; they never lock you in.
