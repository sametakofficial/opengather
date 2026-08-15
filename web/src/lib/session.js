import { api, wantMock } from "./api.js";
import { adaptJob, adaptRun } from "./adapt.js";
import { PAGE_SIZE } from "./constants.js";

export function emptySession() {
  return {
    source: "down",
    health: null,
    status: null,
    version: null,
    runs: [],
    runsTotal: 0,
    run: null,
    jobs: [],
    jobsTotal: 0,
    plugins: [],
    configLive: null,
    errors: {},
  };
}

export async function loadBootstrap() {
  const session = emptySession();
  if (wantMock()) {
    session.source = "down";
    session.errors.health = "mock=1 · live API skipped";
    return session;
  }

  const [health, status, version, runs, plugins, config] = await Promise.allSettled([
    api.getHealth(),
    api.getStatus(),
    api.getVersion(),
    api.listRuns(1, 20),
    api.listPlugins(),
    api.getConfig(),
  ]);

  take(session, "health", health);
  take(session, "status", status);
  take(session, "version", version);

  if (runs.status === "fulfilled") {
    session.runs = (runs.value.items || []).map(adaptRun);
    session.runsTotal = runs.value.total ?? session.runs.length;
  } else {
    session.errors.runs = String(runs.reason);
  }

  if (plugins.status === "fulfilled") {
    session.plugins = plugins.value.items || [];
  } else {
    session.errors.plugins = String(plugins.reason);
  }

  if (config.status === "fulfilled") {
    session.configLive = config.value;
  } else {
    session.errors.config = String(config.reason);
  }

  const reachable =
    health.status === "fulfilled" ||
    status.status === "fulfilled" ||
    runs.status === "fulfilled";
  session.source = reachable ? "api" : "down";
  return session;
}

export async function loadJobsForRun(runId, page = 1) {
  if (!runId) return { jobs: [], total: 0, run: null };
  const [jobsRes, runRes] = await Promise.allSettled([
    api.listJobs({ run_id: runId, page, page_size: PAGE_SIZE }),
    api.getRun(runId),
  ]);
  const jobs =
    jobsRes.status === "fulfilled"
      ? (jobsRes.value.items || []).map(adaptJob)
      : [];
  const total =
    jobsRes.status === "fulfilled"
      ? (jobsRes.value.total ?? jobs.length)
      : 0;
  const run =
    runRes.status === "fulfilled" ? adaptRun(runRes.value) : null;
  return {
    jobs,
    total,
    run,
    error: jobsRes.status === "rejected" ? String(jobsRes.reason) : "",
  };
}

function take(session, key, settled) {
  if (settled.status === "fulfilled") session[key] = settled.value;
  else session.errors[key] = String(settled.reason);
}
