<script>
  import { dump, walkPaths } from "../lib/adapt.js";

  let { snap, selectedJobId } = $props();

  let q = $state("");
  const sample = $derived(snap.jobs.find((j) => j.id === selectedJobId) || snap.jobs[0]);
  const fields = $derived(
    walkPaths(sample?.plugins || {}).filter((f) =>
      !q || f.path.toLowerCase().includes(q.toLowerCase()),
    ),
  );
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://playground</span>
    <span class="pill">no render API</span>
  </div>
  <div class="cols">
    <div class="pane">
      <div class="bar">job.plugins · {sample?.id || "—"}</div>
      <pre class="code">{sample ? dump(sample.plugins) : "select a job from library"}</pre>
    </div>
    <div class="pane">
      <div class="bar">notes</div>
      <div class="out">
        Jinja render and plugin invoke have no HTTP endpoint.<br />
        This page walks the selected job payload only.
        <div class="box">
          <b>available on this job</b><br />
          · job.plugins.*<br />
          · job.input.value / job.output.values<br />
          · run.config snapshot (config screen)
        </div>
      </div>
    </div>
  </div>
  <div class="bottom">
    <div class="half">
      <div class="label mb">plugin invoker</div>
      <div class="row">
        <span class="btn mini" disabled title="no invoke endpoint">▶ invoke disabled</span>
      </div>
      <pre class="dump">{dump(sample?.plugins?.tmdb || { note: "no tmdb key on this job" })}</pre>
    </div>
    <div class="half">
      <div class="label mb">field explorer · this job</div>
      <input class="field" placeholder="filter paths" bind:value={q} />
      <div class="fields">
        {#each fields as f}
          <div>{f.path} <span class="muted">{typeof f.value === "object" ? "" : String(f.value).slice(0, 80)}</span></div>
        {:else}
          <div class="muted">no paths</div>
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .cols { display: flex; flex: 1; min-height: 0; border-bottom: 1.5px solid var(--ink); }
  .pane { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .pane + .pane { border-left: 1.5px solid var(--ink); }
  .bar { padding: 5px 10px; background: var(--paper-2); border-bottom: 1px solid var(--line-2); font-size: 11px; }
  .code, .out {
    flex: 1;
    margin: 0;
    border: none;
    background: #1a1a1a;
    color: #cfc8b0;
    padding: 10px;
    overflow: auto;
    font: inherit;
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .out { background: var(--paper); color: var(--ink); }
  .box { margin-top: 14px; padding: 8px; border: 1px dashed var(--ink); background: var(--paper-2); font-size: 11px; line-height: 1.7; }
  .bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }
  .mb { margin-bottom: 6px; }
  .row { display: flex; gap: 6px; align-items: center; }
  .dump, .fields {
    margin-top: 10px;
    border: 1px solid var(--ink);
    background: var(--paper-2);
    padding: 8px;
    font-size: 11px;
    max-height: 160px;
    overflow: auto;
    white-space: pre-wrap;
  }
</style>
