<script>
  import { dump } from "../lib/adapt.js";

  let { snap, selectedRunId } = $props();

  const live = $derived(snap.configLive);
  const runText = $derived(
    snap.run?.config && Object.keys(snap.run.config).length
      ? dump(snap.run.config)
      : "",
  );
  const liveText = $derived(live?.text || (live?.config ? dump(live.config) : ""));
  let tab = $state("live");
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://config · {tab === "live" ? "config.yml" : `run ${selectedRunId || "—"}`}</span>
    <span class="pill">read-only</span>
  </div>
  <div class="split">
    <aside class="tree">
      <div><b>source</b></div>
      <button class="btn mini" class:active={tab === "live"} onclick={() => (tab = "live")}>live config.yml</button>
      <button class="btn mini" class:active={tab === "run"} onclick={() => (tab = "run")}>this run snapshot</button>
      <div class="muted pad mt">GET /config · secrets stay ${"{ENV}"}</div>
      <div class="label mt">write</div>
      <div class="muted">PUT /config · not in API</div>
    </aside>
    <div class="ed">
      {#if tab === "live"}
        <div class="edbar">▸ GET /config · {live?.path || "config.yml"} · writable={String(live?.writable ?? false)}</div>
        {#if liveText}
          <pre class="code">{liveText}</pre>
        {:else}
          <pre class="code">{snap.errors?.config || "config.yml not served"}</pre>
        {/if}
      {:else}
        <div class="edbar">▸ run.config snapshot · json</div>
        {#if runText}
          <pre class="code">{runText}</pre>
        {:else}
          <pre class="code">no config snapshot on this run.</pre>
        {/if}
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
    display: flex;
    flex-direction: column;
    gap: 6px;
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
