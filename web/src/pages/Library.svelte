<script>
  import { PAGE_SIZE } from "../lib/constants.js";
  import {
    countByCat,
    countByPlugin,
    countByStatus,
    mark,
    markClass,
    pluginColumns,
  } from "../lib/adapt.js";

  let { snap, selectedJobId, selectedRunId, jobPage, onNavigate, onJobPage } = $props();

  let q = $state("");
  let hasFilter = $state("");
  let statusFilter = $state("");
  let catFilter = $state("");

  const jobs = $derived(snap.jobs || []);
  const columns = $derived(pluginColumns(jobs));
  const pluginCounts = $derived(countByPlugin(jobs));
  const catCounts = $derived(countByCat(jobs));
  const statusCounts = $derived(countByStatus(jobs));

  const items = $derived(
    jobs.filter((it) => {
      if (q) {
        const hay = `${it.title} ${it.path} ${it.id}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      if (hasFilter && !it.plugins?.[hasFilter]) return false;
      if (statusFilter && (it.status?.state || "unknown") !== statusFilter) return false;
      if (catFilter && it.cat !== catFilter) return false;
      return true;
    }),
  );

  const pages = $derived(Math.max(1, Math.ceil((snap.jobsTotal || 0) / PAGE_SIZE)));
  const down = $derived(snap.source !== "api");
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://library?run={selectedRunId || "—"}</span>
    <span class="pill">{snap.jobsTotal || 0} jobs</span>
    <span class="pill">page {jobPage}/{pages}</span>
  </div>

  {#if down}
    <div class="banner">daemon unreachable · no mock library. start FastAPI or pass ?mock=1 is not a dataset.</div>
  {:else if !selectedRunId}
    <div class="banner">no run selected · library is the job list of a run.</div>
  {/if}

  <div class="filterbar">
    <div class="row">
      <input class="field" placeholder="search · title, path, id…" bind:value={q} />
      {#if jobPage > 1}
        <button class="btn mini" onclick={() => onJobPage(jobPage - 1)}>‹ prev</button>
      {/if}
      {#if jobPage < pages}
        <button class="btn mini" onclick={() => onJobPage(jobPage + 1)}>next ›</button>
      {/if}
    </div>
    <div class="row chips">
      <span class="label">filters · this page</span>
      {#if hasFilter}<button class="pill fill" onclick={() => (hasFilter = "")}>has:{hasFilter} ✕</button>{/if}
      {#if catFilter}<button class="pill fill" onclick={() => (catFilter = "")}>cat:{catFilter} ✕</button>{/if}
      {#if statusFilter}<button class="pill fill" onclick={() => (statusFilter = "")}>status:{statusFilter} ✕</button>{/if}
      {#if hasFilter || catFilter || statusFilter}
        <button class="btn mini ghost" onclick={() => { hasFilter = ""; catFilter = ""; statusFilter = ""; }}>clear</button>
      {/if}
    </div>
  </div>

  <div class="body">
    <aside class="rail">
      <div class="label">plugin namespaces</div>
      <div class="list">
        {#each pluginCounts as p}
          <button class="chip-row" onclick={() => (hasFilter = p.name)}>
            <span class="pill">● {p.name}</span> <span class="muted">{p.n}</span>
          </button>
        {:else}
          <div class="muted">none on this page</div>
        {/each}
      </div>
      <div class="label">parsed.category</div>
      <div class="list">
        {#each catCounts as p}
          <button class="chip-row" onclick={() => (catFilter = p.name)}>
            <span class="pill">{p.name}</span> <span class="muted">{p.n}</span>
          </button>
        {/each}
      </div>
      <div class="label">status</div>
      <div class="list">
        {#each statusCounts as p}
          <button class="chip-row" onclick={() => (statusFilter = p.name)}>
            <span class="pill">{p.name}</span> <span class="muted">{p.n}</span>
          </button>
        {/each}
      </div>
    </aside>

    <div class="scroll">
      <table class="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>title</th>
            <th>year</th>
            <th>cat</th>
            {#each columns as name}<th>{name}</th>{/each}
            <th>state</th>
            <th>updated</th>
          </tr>
        </thead>
        <tbody>
          {#each items as it}
            <tr
              class="clickable"
              class:sel={it.id === selectedJobId}
              onclick={() => onNavigate("item", { jobId: it.id })}
            >
              <td>{it.index}</td>
              <td>{it.title}</td>
              <td>{it.year ?? "–"}</td>
              <td>{it.cat}</td>
              {#each columns as name}
                <td class="c {markClass(it.marks?.[name])}">{mark(it.marks?.[name] || "no")}</td>
              {/each}
              <td>{it.status?.state || "—"}</td>
              <td>{it.updated}</td>
            </tr>
          {:else}
            <tr><td colspan="8" class="muted">no jobs in this run / page</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  <div class="foot">
    <span>showing {items.length} of {snap.jobsTotal || 0} · page size {PAGE_SIZE}</span>
    <span>library = jobs of {selectedRunId || "—"}</span>
  </div>
</div>

<style>
  .banner {
    padding: 8px 12px;
    background: var(--paper-3);
    border-bottom: 1px solid var(--ink);
    font-size: 11px;
  }
  .filterbar {
    border-bottom: 1.5px solid var(--ink);
    padding: 10px 12px;
    background: var(--paper-2);
  }
  .row { display: flex; gap: 6px; align-items: center; }
  .chips { margin-top: 8px; flex-wrap: wrap; }
  .body { flex: 1; display: flex; overflow: hidden; min-height: 0; }
  .rail {
    width: 220px;
    border-right: 1.5px solid var(--ink);
    padding: 10px;
    background: var(--paper-2);
    overflow: auto;
    font-size: 11.5px;
  }
  .list { margin: 6px 0 12px; line-height: 2; }
  .chip-row {
    display: block;
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0;
  }
  .foot {
    border-top: 1.5px solid var(--ink);
    padding: 6px 12px;
    background: var(--paper-2);
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
</style>
