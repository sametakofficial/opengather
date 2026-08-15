<script>
  let { snap } = $props();

  const groups = $derived.by(() => {
    const g = { per_run: [], parse: [], data: [], output: [] };
    for (const p of snap.plugins || []) {
      const stage = normalize(p.stage);
      (g[stage] || g.output).push(p);
    }
    return g;
  });

  function normalize(stage) {
    if (!stage) return "output";
    if (stage === "input" || stage === "per_run") return "per_run";
    if (["parse", "data", "output"].includes(stage)) return stage;
    return "output";
  }
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://plugins</span>
    <span class="pill">{snap.plugins.length} manifests</span>
  </div>
  {#if snap.errors.plugins}
    <div class="banner">{snap.errors.plugins}</div>
  {/if}
  <div class="grid scroll">
    <section>
      <header class="h in">per_run · input</header>
      <div class="cards">
        {#each groups.per_run as p}
          <article>
            <div><b>{p.name}</b> <span class="muted">v{p.version}</span>
              <span class="pill" class:fill={p.enabled}>{p.enabled ? "enabled" : "off"}</span>
            </div>
            <div class="muted tiny">provides · {(p.provides || []).join(" · ") || "—"}</div>
            <div class="muted tiny">requires · {(p.requires || []).join(" · ") || "—"}</div>
            <div class="tiny">{p.description || ""}</div>
          </article>
        {:else}
          <div class="empty muted">none</div>
        {/each}
      </div>
    </section>
    <section>
      <header class="h parse">parse · per_job</header>
      <div class="cards">
        {#each groups.parse as p}
          <article>
            <div><b>{p.name}</b> <span class="muted">v{p.version}</span>
              <span class="pill" class:fill={p.enabled}>{p.enabled ? "enabled" : "off"}</span>
            </div>
            <div class="muted tiny">provides · {(p.provides || []).join(" · ")}</div>
            <div class="muted tiny">requires · {(p.requires || []).join(" · ") || "—"}</div>
          </article>
        {:else}
          <div class="empty muted">none</div>
        {/each}
      </div>
    </section>
    <section class="wide">
      <header class="h data">data · per_job</header>
      <div class="cards four">
        {#each groups.data as p}
          <article>
            <div><b>{p.name}</b> <span class="muted">v{p.version}</span>
              <span class="pill" class:fill={p.enabled}>{p.enabled ? "on" : "disabled"}</span>
            </div>
            <div class="muted tiny">provides · {(p.provides || []).join(" · ")}</div>
            <div class="muted tiny">requires · {(p.requires || []).join(" · ")}</div>
          </article>
        {:else}
          <div class="empty muted">none</div>
        {/each}
      </div>
    </section>
    <section class="wide">
      <header class="h out">output · per_job</header>
      <div class="cards">
        {#each groups.output as p}
          <article>
            <div><b>{p.name}</b> <span class="muted">v{p.version}</span>
              <span class="pill" class:fill={p.enabled}>{p.enabled ? "enabled" : "off"}</span>
            </div>
            <div class="muted tiny">provides · {(p.provides || []).join(" · ")}</div>
            <div class="muted tiny">requires · {(p.requires || []).join(" · ")}</div>
          </article>
        {:else}
          <div class="empty muted">none</div>
        {/each}
      </div>
    </section>
  </div>
</div>

<style>
  .banner { padding: 8px 12px; background: var(--paper-3); border-bottom: 1px solid var(--ink); font-size: 11px; }
  .grid { padding: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .wide { grid-column: 1 / -1; }
  section { border: 1px solid var(--ink); background: var(--paper); }
  header.h { border-bottom: 1px solid var(--ink); padding: 6px 10px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
  .h.in { background: var(--hi); }
  .h.parse { background: var(--hi-2); }
  .h.data { background: var(--paper-3); }
  .h.out { background: var(--ink); color: var(--paper); }
  .cards { padding: 10px; display: flex; flex-direction: column; gap: 8px; }
  .cards.four { display: grid; grid-template-columns: repeat(4, 1fr); }
  article { border: 1px solid var(--ink); padding: 8px; background: var(--paper-2); }
  .tiny { font-size: 11px; margin-top: 4px; }
  .empty { padding: 10px; }
</style>
