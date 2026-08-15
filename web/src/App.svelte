<script>
  import { onMount } from "svelte";
  import { NAV } from "./lib/constants.js";
  import { api, ApiError } from "./lib/api.js";
  import { loadBootstrap, loadJobsForRun, emptySession } from "./lib/session.js";
  import { RUN_TIMEOUT_MS } from "./lib/constants.js";
  import Dashboard from "./pages/Dashboard.svelte";
  import Library from "./pages/Library.svelte";
  import ItemDetail from "./pages/ItemDetail.svelte";
  import Runs from "./pages/Runs.svelte";
  import Plugins from "./pages/Plugins.svelte";
  import Config from "./pages/Config.svelte";
  import Playground from "./pages/Playground.svelte";
  import Diagnostics from "./pages/Diagnostics.svelte";

  let page = $state("dashboard");
  let snap = $state(emptySession());
  let selectedRunId = $state("");
  let selectedJobId = $state("");
  let jobPage = $state(1);
  let busy = $state(false);
  let notice = $state("");
  let booted = $state(false);

  async function boot() {
    snap = await loadBootstrap();
    if (!selectedRunId && snap.runs[0]) selectedRunId = snap.runs[0].id;
    if (selectedRunId) await loadJobs();
    booted = true;
  }

  async function loadJobs() {
    if (!selectedRunId) {
      snap = { ...snap, jobs: [], jobsTotal: 0, run: null };
      return;
    }
    const pack = await loadJobsForRun(selectedRunId, jobPage);
    snap = {
      ...snap,
      jobs: pack.jobs,
      jobsTotal: pack.total,
      run: pack.run,
    };
    if (pack.error) notice = pack.error.slice(0, 220);
    if (selectedJobId && !pack.jobs.some((j) => j.id === selectedJobId)) {
      selectedJobId = pack.jobs[0]?.id || "";
    } else if (!selectedJobId && pack.jobs[0]) {
      selectedJobId = pack.jobs[0].id;
    }
  }

  onMount(boot);

  function go(id, extra) {
    page = id;
    if (extra?.jobId) selectedJobId = extra.jobId;
    if (extra?.runId && extra.runId !== selectedRunId) {
      selectedRunId = extra.runId;
      jobPage = 1;
      loadJobs();
    }
  }

  async function selectRun(id) {
    if (!id || id === selectedRunId) return;
    selectedRunId = id;
    selectedJobId = "";
    jobPage = 1;
    await loadJobs();
  }

  async function changeJobPage(next) {
    jobPage = next;
    await loadJobs();
  }

  async function newRun() {
    busy = true;
    notice = "POST /runs · blocking until orchestrator returns…";
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), RUN_TIMEOUT_MS);
    try {
      const run = await api.createRun({ dry_run: true }, { signal: ctrl.signal });
      notice = `run ${run.id} · ${run.status?.state || "done"} · persisted ${run.persistence?.persisted ?? "?"}`;
      await boot();
      selectedRunId = run.id;
      await loadJobs();
      page = "library";
    } catch (err) {
      if (err.name === "AbortError") {
        notice = `run timed out after ${RUN_TIMEOUT_MS / 1000}s`;
      } else if (err instanceof ApiError) {
        notice = err.message;
      } else {
        notice = String(err.message || err);
      }
    } finally {
      clearTimeout(timer);
      busy = false;
    }
  }

  const pages = {
    dashboard: Dashboard,
    library: Library,
    item: ItemDetail,
    runs: Runs,
    plugins: Plugins,
    config: Config,
    playground: Playground,
    diagnostics: Diagnostics,
  };

  const ctx = $derived({
    snap,
    selectedRunId,
    selectedJobId,
    jobPage,
    onNavigate: go,
    onSelectRun: selectRun,
    onJobPage: changeJobPage,
  });
</script>

<div class="shell">
  <aside class="nav-side">
    <div class="nav-grp">
      <span class="label">system</span>
      {#each NAV as item}
        <button
          class="nav-item"
          class:active={page === item.id}
          onclick={() => go(item.id)}
        >
          <span class="ic">{item.icon}</span>{item.label}
        </button>
      {/each}
    </div>
    <div class="nav-grp">
      <span class="label">run</span>
      <select
        class="field run-sel"
        value={selectedRunId}
        onchange={(e) => selectRun(e.currentTarget.value)}
      >
        {#if !snap.runs.length}
          <option value="">no runs</option>
        {/if}
        {#each snap.runs as run}
          <option value={run.id}>{run.id} · {run.status}</option>
        {/each}
      </select>
    </div>
    <div class="nav-grp last">
      <span class="label">actions</span>
      <button class="nav-item" onclick={newRun} disabled={busy || snap.source !== "api"}>
        <span class="ic">▶</span>{busy ? "running…" : "new run…"}
      </button>
      <button class="nav-item" onclick={boot}>
        <span class="ic">↻</span>refresh
      </button>
    </div>
    <div class="foot">
      <div>
        daemon ·
        <span class={snap.source === "api" ? "ok" : "muted"}>
          {snap.source === "api" ? "up" : "unreachable"}
        </span>
      </div>
      <div>build · {snap.version?.version || "—"}</div>
      {#if notice}
        <div class="notice">{notice}</div>
      {/if}
    </div>
  </aside>

  <main class="stage">
    {#if !booted}
      <div class="boot">loading…</div>
    {:else}
      {@const C = pages[page]}
      <C {...ctx} />
    {/if}
  </main>
</div>

<style>
  .shell { display: flex; height: 100%; min-height: 0; }
  .nav-side {
    width: 200px;
    border-right: 1.5px solid var(--ink);
    background: var(--paper-2);
    display: flex;
    flex-direction: column;
  }
  .nav-grp { padding: 10px 12px 6px; border-bottom: 1px solid var(--line-2); }
  .nav-grp.last { border-bottom: none; }
  .nav-grp .label { margin-bottom: 6px; display: block; }
  .run-sel { font-size: 11px; }
  .nav-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 5px 10px;
    font-size: 12px;
    border: 1px solid transparent;
    margin: 0 0 4px;
    background: transparent;
  }
  .nav-item:hover { border-color: var(--ink); }
  .nav-item.active { background: var(--ink); color: var(--paper); }
  .nav-item:disabled { opacity: 0.45; cursor: default; }
  .nav-item .ic { display: inline-block; width: 14px; text-align: center; margin-right: 6px; }
  .foot {
    margin-top: auto;
    padding: 10px 12px;
    border-top: 1px solid var(--line-2);
    font-size: 11px;
    color: var(--muted);
  }
  .notice { margin-top: 8px; color: var(--ink); word-break: break-word; }
  .stage { flex: 1; min-width: 0; min-height: 0; }
  .boot { padding: 24px; }
</style>
