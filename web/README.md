# archivarr web

Vite + Svelte 5 panel. It does **not** change the Python runtime.
It reads the existing FastAPI surface and renders the v2 sitemap.

```
cd web
npm install
npm run dev
```

http://127.0.0.1:5173  →  proxies `/api` to `http://127.0.0.1:8080`

`:8000` is often another service on this host. Start Archiverr on 8080:

```
cd /home/samet/Workspace/archiver
.venv/bin/python -m archiverr serve --host 127.0.0.1 --port 8080
```

Override the proxy with `ARCHIVERR_API=http://127.0.0.1:PORT npm run dev`.

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

## S45 API the panel uses

- `GET /api/v1/config` — masked live `config.yml` (read-only)
- `POST /api/v1/render` — Jinja against a persisted run/job
- `GET /api/v1/runs/{id}` now includes `data` (core envelope)

## Not in the API (screens stay honest)

log stream · websocket · `PUT /config` · plugin invoke · items collection.
