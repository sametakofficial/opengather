import { MERGE_ORDER } from "./constants.js";

export function getPath(obj, path) {
  if (obj == null || !path) return undefined;
  const parts = String(path).split(".");
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[p];
  }
  return cur;
}

export function formatWhen(value) {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString("en-GB", { hour12: false });
  } catch {
    return String(value);
  }
}

export function formatMs(ms) {
  if (ms == null || ms === 0) return "—";
  const s = Math.round(Number(ms) / 1000);
  if (Number.isNaN(s)) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function basename(path) {
  if (!path) return "";
  return String(path).split("/").pop();
}

export function mark(v) {
  if (v === "yes" || v === "ok") return "✓";
  if (v === "fail" || v === "err") return "✗";
  if (v === "skip") return "skip";
  if (v === "empty") return "·";
  return "–";
}

export function markClass(v) {
  if (v === "fail" || v === "err") return "err";
  if (v === "skip") return "warn";
  if (!v || v === "no" || v === "na") return "muted";
  return "";
}

export function adaptRun(doc) {
  const st = doc.status || {};
  const state = st.state || "pending";
  let status = state;
  if (state === "success") status = "ok";
  else if (st.failed) status = `${st.failed} failed`;
  const jobList = Array.isArray(doc.jobs) ? doc.jobs : [];
  return {
    id: doc.id,
    started: formatWhen(doc.created_at),
    duration: formatMs(st.duration_ms),
    jobs: st.total_jobs ?? jobList.length,
    completed: st.completed ?? 0,
    failed: st.failed ?? 0,
    status,
    state,
    config: doc.config || {},
    options: doc.options || {},
    persistence: doc.persistence || null,
    raw: doc,
  };
}

export function adaptJob(doc) {
  const plugins = asObject(doc.plugins);
  const parsed = pickParsed(plugins);
  return {
    id: doc.id,
    run_id: doc.run_id || "",
    index: doc.index ?? 0,
    title: parsed.title || basename(doc.input?.value) || doc.id,
    year: parsed.year ?? null,
    cat: parsed.cat || "?",
    marks: pluginMarks(plugins, doc.status),
    status: doc.status || {},
    updated: formatWhen(doc.completed_at || doc.created_at),
    path: doc.input?.value || "",
    input: doc.input || { value: "", data: {} },
    output: doc.output || { values: [], data: {} },
    plugins,
    raw: doc,
  };
}

export function pickParsed(plugins) {
  const r = plugins.renamer || {};
  const parsed = r.parsed || r;
  const movie = parsed.movie || {};
  const show = parsed.show || {};
  if (movie.name || movie.title) {
    return { title: movie.name || movie.title, year: movie.year ?? null, cat: "movie" };
  }
  if (show.name || show.title) {
    const ep = show.episode_title ? ` — ${show.episode_title}` : "";
    const se =
      show.season_number != null && show.episode_number != null
        ? ` S${String(show.season_number).padStart(2, "0")}E${String(show.episode_number).padStart(2, "0")}`
        : "";
    return {
      title: `${show.name || show.title}${se}${ep}`,
      year: show.year ?? null,
      cat: "show",
    };
  }
  const tmdb = plugins.tmdb || {};
  const movieTitle = titleOf(tmdb.movie);
  const showTitle = titleOf(tmdb.show);
  if (movieTitle) {
    return { title: movieTitle, year: yearOf(tmdb.movie), cat: "movie" };
  }
  if (showTitle) {
    return { title: showTitle, year: yearOf(tmdb.show), cat: "show" };
  }
  return { title: "", year: null, cat: "?" };
}

function titleOf(entity) {
  if (!entity) return "";
  const t = entity.title;
  if (typeof t === "string") return t;
  if (t && typeof t === "object") return t.primary || t.original || "";
  return entity.name || "";
}

function yearOf(entity) {
  if (!entity) return null;
  return entity.year ?? entity.release_year ?? entity.release?.year ?? null;
}

function pluginMarks(plugins, status) {
  const failed = new Set(status?.failed || []);
  const skipped = new Set(status?.skipped || []);
  const marks = {};
  for (const [name, payload] of Object.entries(plugins)) {
    if (failed.has(name)) marks[name] = "fail";
    else if (skipped.has(name)) marks[name] = "skip";
    else if (payload && typeof payload === "object" && Object.keys(payload).length)
      marks[name] = "yes";
    else marks[name] = "empty";
  }
  return marks;
}

function asObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value;
}

/** First-listed provider wins. UI estimate — not run.data. */
export function mergePlugins(plugins, order = MERGE_ORDER) {
  const merged = {};
  const source = {};
  for (const name of [...order].reverse()) {
    const payload = plugins[name];
    if (payload && typeof payload === "object") {
      deepAssign(merged, payload, name, source, "");
    }
  }
  return { merged, source };
}

function deepAssign(target, src, plugin, sourceMap, prefix) {
  if (!src || typeof src !== "object" || Array.isArray(src)) return;
  for (const [k, v] of Object.entries(src)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      if (!target[k] || typeof target[k] !== "object" || Array.isArray(target[k])) {
        target[k] = {};
      }
      deepAssign(target[k], v, plugin, sourceMap, path);
    } else {
      target[k] = v;
      sourceMap[path] = plugin;
    }
  }
}

export function extractGeneral(merged, job) {
  const movie = merged.movie || {};
  const show = merged.show || {};
  const entity = titleOf(movie) ? movie : titleOf(show) ? show : movie;
  const ids = entity.ids || {};
  const genres = entity.genres;
  return {
    title: titleOf(entity) || job?.title || "—",
    year: yearOf(entity) ?? job?.year ?? "—",
    imdb: ids.imdb || entity.imdb_id || "—",
    tmdb: ids.tmdb || entity.id || "—",
    release: entity.release_date || entity.release?.date || entity.first_air_date || "—",
    cert: entity.certification || entity.rated || "—",
    runtime: formatRuntime(entity.runtime || entity.episode_runtime),
    genres: Array.isArray(genres) ? genres.join(", ") : genres || "—",
    production:
      entity.production ||
      firstName(entity.production_companies) ||
      entity.studio ||
      "—",
    country: firstName(entity.production_countries) || entity.country || "—",
    langs: entity.original_language || firstName(entity.spoken_languages) || "—",
    rating: entity.vote_average ?? entity.rating ?? "—",
    votes: entity.vote_count ?? entity.votes ?? "—",
    tagline: entity.tagline || "",
    plot: entity.overview || entity.plot || "",
  };
}

function formatRuntime(v) {
  if (v == null || v === "") return "—";
  if (typeof v === "string") return v;
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  if (n > 300) {
    const h = Math.floor(n / 3600);
    const m = Math.round((n % 3600) / 60);
    return h ? `${h}h ${m}m` : `${m}m`;
  }
  const h = Math.floor(n / 60);
  const m = n % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function firstName(list) {
  if (!Array.isArray(list) || !list.length) return "";
  const x = list[0];
  if (typeof x === "string") return x;
  return x?.name || x?.english_name || "";
}

export function pluginColumns(jobs) {
  const names = new Set();
  for (const job of jobs) {
    for (const n of Object.keys(job.plugins || {})) names.add(n);
  }
  return [...names].sort();
}

export function countByPlugin(jobs) {
  const counts = {};
  for (const job of jobs) {
    for (const n of Object.keys(job.plugins || {})) {
      counts[n] = (counts[n] || 0) + 1;
    }
  }
  return Object.entries(counts)
    .map(([name, n]) => ({ name, n }))
    .sort((a, b) => b.n - a.n);
}

export function countByCat(jobs) {
  const counts = {};
  for (const job of jobs) {
    const c = job.cat || "?";
    counts[c] = (counts[c] || 0) + 1;
  }
  return Object.entries(counts).map(([name, n]) => ({ name, n }));
}

export function countByStatus(jobs) {
  const counts = {};
  for (const job of jobs) {
    const s = job.status?.state || "unknown";
    counts[s] = (counts[s] || 0) + 1;
  }
  return Object.entries(counts).map(([name, n]) => ({ name, n }));
}

export function stageOf(name, manifests = []) {
  const m = manifests.find((p) => p.name === name);
  const stage = m?.stage;
  if (stage === "per_run" || stage === "input") return "in";
  if (stage === "parse" || stage === "data" || stage === "output") return stage;
  if (["scanner", "file-reader"].includes(name)) return "in";
  if (["renamer", "ffprobe"].includes(name)) return "parse";
  if (["tmdb", "omdb", "tvdb", "tvmaze"].includes(name)) return "data";
  if (["tasker", "nfo", "subtitle"].includes(name)) return "output";
  return "";
}

export function walkPaths(obj, prefix = "", out = [], depth = 0) {
  if (obj == null || depth > 8) return out;
  if (typeof obj !== "object") {
    out.push({ path: prefix, value: obj });
    return out;
  }
  if (Array.isArray(obj)) {
    out.push({ path: prefix, value: `list(${obj.length})` });
    if (obj[0] && typeof obj[0] === "object") walkPaths(obj[0], `${prefix}[0]`, out, depth + 1);
    return out;
  }
  const keys = Object.keys(obj);
  if (!prefix) {
    for (const k of keys) walkPaths(obj[k], k, out, depth + 1);
    return out;
  }
  if (!keys.length) {
    out.push({ path: prefix, value: "{}" });
    return out;
  }
  for (const k of keys) walkPaths(obj[k], `${prefix}.${k}`, out, depth + 1);
  return out;
}

export function dump(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}
