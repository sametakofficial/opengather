<script>
  import { api } from "../lib/api.js";
  import { walkPaths } from "../lib/adapt.js";

  let { snap, selectedJobId, selectedRunId } = $props();

  let q = $state("");
  let template = $state("{{ data[0].show.title.primary or job.plugins.tmdb.movie.title.primary }}");
  let rendered = $state("");
  let renderErr = $state("");
  let busy = $state(false);

  const sample = $derived(snap.jobs.find((j) => j.id === selectedJobId) || snap.jobs[0]);
  const fields = $derived(
    walkPaths(sample?.plugins || {}).filter((f) =>
      !q || f.path.toLowerCase().includes(q.toLowerCase()),
    ),
  );

  async function runRender() {
    if (!selectedRunId && !snap.run?.id) {
      renderErr = "select a run first";
      return;
    }
    busy = true;
    renderErr = "";
    try {
      const out = await api.renderTemplate({
        template,
        run_id: selectedRunId || snap.run?.id,
        job_id: sample?.id,
        job_index: sample?.index,
      });
      rendered = out.rendered;
      if (out.error) renderErr = "engine reported Template error";
    } catch (e) {
      renderErr = String(e.message || e);
      rendered = "";
    } finally {
      busy = false;
    }
  }
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://playground</span>
    <span class="pill">POST /render</span>
  </div>
  <div class="cols">
    <div class="pane">
      <div class="bar">template · same engine as tasker</div>
      <textarea class="code edit" bind:value={template}></textarea>
    </div>
    <div class="pane">
      <div class="bar">rendered · {sample?.id || "no job"}</div>
      <pre class="code">{rendered || (renderErr ? renderErr : "press render")}</pre>
    </div>
  </div>
  <div class="bottom">
    <div class="half">
      <div class="label mb">playground</div>
      <div class="row">
        <button class="btn mini" disabled={busy} onclick={runRender}>{busy ? "…" : "▶ render"}</button>
        <span class="muted">{selectedRunId || "—"}</span>
      </div>
      {#if renderErr}
        <div class="muted mt">{renderErr}</div>
      {/if}
      <div class="box">
        · data.&lt;index&gt;.&lt;cat&gt;.* (core envelope)<br />
        · jobs[job_id].plugins.&lt;name&gt;.*<br />
        · job.input.value<br />
        invoke / write still not in API
      </div>
    </div>
    <div class="half">
      <div class="label mb">field explorer · this job.plugins</div>
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
  .code {
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
  .edit { resize: none; outline: none; }
  .box { margin-top: 14px; padding: 8px; border: 1px dashed var(--ink); background: var(--paper-2); font-size: 11px; line-height: 1.7; }
  .bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }
  .mb { margin-bottom: 6px; }
  .mt { margin-top: 8px; }
  .row { display: flex; gap: 6px; align-items: center; }
  .fields {
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
