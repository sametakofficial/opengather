<script>
  let { snap } = $props();
  const db = $derived(snap.status?.database || {});
  const sys = $derived(snap.status?.system || {});
  const errs = $derived(Object.entries(snap.errors || {}));
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://diagnostics</span>
  </div>
  <div class="pad scroll">
    <div class="stats">
      <div class="card">
        <div class="label">api</div>
        <div class="n sm">{snap.source === "api" ? "live" : "down"}</div>
        <div class="muted">{snap.health?.status || "offline"}</div>
      </div>
      <div class="card">
        <div class="label">database</div>
        <div class="n sm">{db.connected ? "up" : "n/a"}</div>
        <div class="muted">{db.backend || "—"} · {db.database || ""}</div>
      </div>
      <div class="card">
        <div class="label">version</div>
        <div class="n sm">{snap.version?.version || "—"}</div>
        <div class="muted">{snap.version?.python_version || ""}</div>
      </div>
      <div class="card">
        <div class="label">host</div>
        <div class="n sm">{sys.hostname || "—"}</div>
        <div class="muted">{sys.platform || ""} {sys.platform_version || ""}</div>
      </div>
    </div>
    <div class="label mt">collections</div>
    <table class="tbl mt6">
      <thead>
        <tr><th>name</th><th>count</th></tr>
      </thead>
      <tbody>
        {#each Object.entries(db.collections || {}) as [k, v]}
          <tr><td>{k}</td><td>{v}</td></tr>
        {:else}
          <tr><td colspan="2" class="muted">status.database.collections empty</td></tr>
        {/each}
      </tbody>
    </table>
    <div class="label mt">fetch errors</div>
    <table class="tbl mt6">
      <thead>
        <tr><th>call</th><th>error</th></tr>
      </thead>
      <tbody>
        {#each errs as [k, v]}
          <tr><td>{k}</td><td>{v}</td></tr>
        {:else}
          <tr><td colspan="2" class="muted">none</td></tr>
        {/each}
      </tbody>
    </table>
    <div class="label mt">not in API</div>
    <div class="card tiny">
      log stream · websocket · live config.yml · rate-limit meters · items catalog
    </div>
  </div>
</div>

<style>
  .pad { padding: 14px; }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .mt { margin-top: 18px; }
  .mt6 { margin-top: 6px; }
  .tiny { font-size: 11px; line-height: 1.7; }
</style>
