# archivarr web

Vite + Svelte 5 panel. It does **not** change the Python runtime.
It reads the existing FastAPI surface and renders the v2 sitemap.

```
cd web
npm install
npm run dev
```

http://127.0.0.1:5173  →  proxies `/api` to `http://127.0.0.1:8000`

Start the API from the repo root, e.g.

```
uvicorn archiverr.api.main:app --reload --app-dir src
```

(or whatever command you already use).

## Behaviour

- Library = jobs of the **selected run** (`GET /jobs?run_id=`), not a permanent catalog.
- Item detail reads `job.plugins` / `input` / `output`. The All tab is a
  client merge (`tmdb > omdb > tvdb > tvmaze`), labelled as such —
  `runs.data` is not on `RunResponse`.
- Daemon down → empty shells + error text. No Aladdin mock.
- `?mock=1` skips the API on purpose (still no fake dataset).
- `new run` is `POST /runs {dry_run:true}` and **blocks** until the
  orchestrator returns (5 minute abort).

## Not in the API (screens stay honest)

log stream · websocket · live `config.yml` write · plugin invoke ·
Jinja render · items collection.
