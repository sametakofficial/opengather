<script>
  import { stageOf } from "../lib/adapt.js";

  let { snap, selectedRunId, selectedJobId, onNavigate, onSelectRun } = $props();

  const run = $derived(snap.runs.find((r) => r.id === selectedRunId) || snap.run);
  const jobs = $derived(snap.jobs || []);
  const selected = $derived(jobs.find((j) => j.id === selectedJobId) || jobs[0]);

  const stages = $derived.by(() => {
    const g = { in: [], parse: [], data: [], output: [] };
    for (const p of snap.plugins || []) {
      const s = stageOf(p.name, snap.plugins) || "output";
      (g[s] || g.output).push(p.name);
    }
    return g;
  });

  function countStage(names) {
    if (!jobs.length || !names.length) return "—";
    let n = 0;
    for (const job of jobs) {
      if (names.some((name) => job.plugins?.[name])) n += 1;
    }
    return `${n}/${jobs.length}`;
  }
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://runs/{run?.id || "—"} · {run?.status || "idle"}</span>
  </div>

  <div class="stages">
    <span class="label">stage · from manifests + this page</span>
    <div class="stg hi">
      <div class="nm">per_run · input</div>
      <div>{stages.in.join(" · ") || "—"} · {countStage(stages.in)}</div>
    </div>
    <span>→</span>
    <div class="stg hi2">
      <div class="nm">parse</div>
      <div>{stages.parse.join(" · ") || "—"} · {countStage(stages.parse)}</div>
    </div>
    <span>→</span>
    <div class="stg p3">
      <div class="nm">data</div>
      <div>{stages.data.join(" · ") || "—"} · {countStage(stages.data)}</div>
    </div>
    <span>→</span>
    <div class="stg">
      <div class="nm">output</div>
      <div>{stages.output.join(" · ") || "—"} · {countStage(stages.output)}</div>
    </div>
    <span class="sum">
      <span class="pill">{run?.jobs ?? jobs.length} jobs</span>
      <span class="pill fill">{run?.status || "idle"}</span>
    </span>
  </div>

  <div class="picker">
    <span class="label">runs</span>
    {#each snap.runs as r}
      <button class="btn mini" class:active={r.id === selectedRunId} onclick={() => onSelectRun(r.id)}>{r.id}</button>
    {:else}
      <span class="muted">none</span>
    {/each}
  </div>

  <div class="main">
    <div class="logcol">
      <div class="logbar">
        <span class="muted">log stream</span>
      </div>
      <pre class="term">no log stream in API.
GET /runs/&lt;id&gt;/status exists for polling.
WebSocket /stream is advertised in OpenAPI text only — no router.

selected · {run?.id || "—"}
state · {run?.state || run?.status || "—"}
duration · {run?.duration || "—"}
persistence · {run?.persistence?.mode || "—"} / {run?.persistence?.persisted ?? "—"}</pre>
    </div>
    <aside class="insp">
      <div class="label">selected job · {selected?.title || "—"}</div>
      <div class="muted tiny">{selected?.id || "no job on this page"}</div>
      <div class="label mt">plugin keys</div>
      <table class="tbl mt6">
        <thead>
          <tr><th>plugin</th><th>mark</th></tr>
        </thead>
        <tbody>
          {#each Object.entries(selected?.marks || {}) as [name, mark]}
            <tr>
              <td>{name}</td>
              <td>{mark}</td>
            </tr>
          {:else}
            <tr><td colspan="2" class="muted">empty</td></tr>
          {/each}
        </tbody>
      </table>
      {#if selected}
        <div class="mt">
          <button class="btn mini" onclick={() => onNavigate("item", { jobId: selected.id })}>open item detail →</button>
        </div>
      {/if}
    </aside>
  </div>
</div>

<style>
  .stages {
    border-bottom: 1.5px solid var(--ink);
    background: var(--paper-2);
    padding: 10px 14px;
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }
  .picker {
    border-bottom: 1px solid var(--ink);
    padding: 8px 12px;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
    background: var(--paper);
  }
  .stg { border: 1px solid var(--ink); padding: 5px 10px; font-size: 11px; background: var(--paper); }
  .stg.hi { background: var(--hi); }
  .stg.hi2 { background: var(--hi-2); }
  .stg.p3 { background: var(--paper-3); }
  .nm { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
  .sum { margin-left: auto; font-size: 11px; color: var(--muted); }
  .main { flex: 1; display: flex; min-height: 0; overflow: hidden; }
  .logcol { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .logbar {
    padding: 6px 10px;
    border-bottom: 1px solid #333;
    background: #0e0e0e;
    color: #cfc8b0;
    font-size: 11px;
  }
  .insp {
    width: 320px;
    border-left: 1.5px solid var(--ink);
    padding: 12px;
    background: var(--paper);
    overflow: auto;
  }
  .tiny { font-size: 11px; }
  .mt { margin-top: 12px; }
  .mt6 { margin-top: 6px; }
</style>
