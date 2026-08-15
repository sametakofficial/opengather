<script>
  import { countByPlugin, stageOf } from "../lib/adapt.js";

  let { snap, selectedRunId, onNavigate, onSelectRun } = $props();

  const runs = $derived(snap.runs || []);
  const jobs = $derived(snap.jobs || []);
  const plugins = $derived(snap.plugins || []);
  const last = $derived(runs.find((r) => r.id === selectedRunId) || runs[0]);
  const okPlugins = $derived(plugins.filter((p) => p.enabled !== false).length);
  const bars = $derived(
    countByPlugin(jobs).map((row) => ({
      ...row,
      stage: stageOf(row.name, plugins) || "data",
      pct: jobs.length ? Math.round((row.n / jobs.length) * 100) : 0,
    })),
  );
  const opts = $derived(last?.options || last?.config?.options || {});
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://dashboard</span>
    <span class="pill" class:fill={snap.source === "api"}>
      ● {snap.source === "api" ? "daemon up" : "unreachable"}
    </span>
  </div>
  <div class="scroll pad">
    <div class="stats">
      <div class="card">
        <div class="label">jobs in selected run</div>
        <div class="n">{snap.jobsTotal || 0}</div>
        <div class="muted">{selectedRunId || "no run"} · page {jobs.length}</div>
      </div>
      <div class="card">
        <div class="label">last run</div>
        <div class="n sm">{last ? `${last.jobs} · ${last.status}` : "—"}</div>
        <div class="muted">{last?.id || "GET /runs empty"}</div>
      </div>
      <div class="card">
        <div class="label">plugins listed</div>
        <div class="n">{okPlugins} / {plugins.length || 0}</div>
        <div class="muted">GET /plugins</div>
      </div>
      <div class="card">
        <div class="label">options snapshot</div>
        <div class="n sm">{opts.dry_run === false ? "live" : "dry-run"}</div>
        <div class="muted">hardlink · {opts.hardlink ?? "—"}</div>
      </div>
    </div>

    <div class="cols">
      <div>
        <div class="label mb">recent runs</div>
        <table class="tbl">
          <thead>
            <tr>
              <th>run</th><th>started</th><th>duration</th><th>jobs</th><th>status</th>
            </tr>
          </thead>
          <tbody>
            {#each runs as run}
              <tr
                class="clickable"
                class:sel={run.id === selectedRunId}
                onclick={() => { onSelectRun(run.id); onNavigate("library"); }}
              >
                <td>{run.id}</td>
                <td>{run.started}</td>
                <td>{run.duration}</td>
                <td>{run.jobs}</td>
                <td>
                  <span class="pill" class:fill={run.status === "ok"} class:fill-2={run.status !== "ok"}>{run.status}</span>
                </td>
              </tr>
            {:else}
              <tr><td colspan="5" class="muted">no runs in Mongo</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div>
        <div class="label mb">plugin keys · this page of jobs</div>
        <div class="card">
          {#each bars as row}
            <div class="prow">
              <span>{row.name} <span class="bdg {row.stage}">{row.stage[0]}</span></span>
              <div class="bar"><i style="width:{row.pct}%"></i></div>
              <span>{row.n}</span>
            </div>
          {:else}
            <div class="muted">no job payloads loaded</div>
          {/each}
        </div>
        <div class="label mb mt">health</div>
        <div class="card tiny">
          daemon ........ <span class={snap.source === "api" ? "ok" : "muted"}>[ {snap.source === "api" ? "up" : "down"} ]</span><br />
          mongodb ....... <span class={snap.status?.database?.connected ? "ok" : "muted"}>[ {snap.status?.database?.connected ? "reachable" : "unknown"} ]</span><br />
          api ........... <span class="muted">[ {snap.health?.status || "offline"} ]</span>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .pad { padding: 14px; }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .cols { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; margin-top: 14px; }
  .mb { margin-bottom: 6px; }
  .mt { margin-top: 14px; }
  .prow {
    display: grid;
    grid-template-columns: 120px 1fr 50px;
    gap: 8px;
    align-items: center;
    font-size: 11px;
    margin: 3px 0;
  }
  .tiny { font-size: 11px; line-height: 1.7; }
</style>
