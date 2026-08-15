<script>
  import { dump } from "../lib/adapt.js";

  let { snap, selectedRunId } = $props();

  const text = $derived(
    snap.run?.config && Object.keys(snap.run.config).length
      ? dump(snap.run.config)
      : "",
  );
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://config · run {selectedRunId || "—"}</span>
    <span class="pill">read-only</span>
  </div>
  <div class="split">
    <aside class="tree">
      <div><b>source</b></div>
      <div class="pad">GET /runs/{"{id}"} .config</div>
      <div class="muted pad">live config.yml is not served</div>
      <div class="label mt">write</div>
      <div class="muted">PUT /config · not in API</div>
    </aside>
    <div class="ed">
      <div class="edbar">▸ run.config snapshot · json</div>
      {#if text}
        <pre class="code">{text}</pre>
      {:else}
        <pre class="code">no config snapshot on this run.
select a persisted run or trigger POST /runs.</pre>
      {/if}
      <div class="edbar">save disabled · no config write endpoint</div>
    </div>
  </div>
</div>

<style>
  .split { flex: 1; display: flex; min-height: 0; }
  .tree {
    width: 200px;
    border-right: 1.5px solid var(--ink);
    padding: 10px;
    background: var(--paper-2);
    font-size: 11px;
    line-height: 1.8;
  }
  .pad { padding-left: 4px; }
  .mt { margin-top: 14px; }
  .ed { flex: 1; display: flex; flex-direction: column; background: #1a1a1a; color: #cfc8b0; min-width: 0; }
  .edbar {
    background: #0e0e0e;
    padding: 5px 10px;
    border-bottom: 1px solid #333;
    font-size: 11px;
    color: #888;
  }
  .edbar:last-child { border-top: 1px solid #333; border-bottom: none; }
  .code {
    flex: 1;
    margin: 0;
    background: #1a1a1a;
    color: #cfc8b0;
    padding: 10px 12px;
    overflow: auto;
    line-height: 1.6;
    font-size: 12px;
    white-space: pre-wrap;
  }
</style>
