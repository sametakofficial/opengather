<script>
  import { CATEGORIES } from "../lib/constants.js";
  import {
    dump,
    extractGeneral,
    mark,
    markClass,
    envelopeForJob,
    mergePlugins,
    stageOf,
  } from "../lib/adapt.js";

  let { snap, selectedJobId, onNavigate } = $props();

  let io = $state("output");
  let plugin = $state("all");
  let category = $state("general");
  let q = $state("");

  const items = $derived(snap.jobs || []);
  const selected = $derived(items.find((x) => x.id === selectedJobId) || items[0] || null);
  const pluginTabs = $derived(["all", ...Object.keys(selected?.plugins || {})]);
  const mergedPack = $derived(mergePlugins(selected?.plugins || {}));
  const envelope = $derived(envelopeForJob(snap.run?.data, selected?.index));
  const allSource = $derived(envelope || mergedPack.merged);
  const general = $derived(extractGeneral(allSource, selected));
  const inspected = $derived(
    plugin === "all" ? allSource : selected?.plugins?.[plugin] || {},
  );
  const pipeline = $derived(Object.keys(selected?.plugins || {}));

  const filtered = $derived(
    items.filter((it) => {
      if (!q) return true;
      return `${it.path} ${it.title} ${it.id}`.toLowerCase().includes(q.toLowerCase());
    }),
  );

  const outputs = $derived(selected?.output?.values || []);
  const otherKeys = $derived(Object.keys(inspected || {}));

  $effect(() => {
    const names = ["all", ...Object.keys(selected?.plugins || {})];
    if (!names.includes(plugin)) plugin = "all";
  });
</script>

<div class="win">
  <div class="win-bar">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span class="url">archivarr://library/item/{selected?.id || "—"}</span>
    <button class="btn mini" onclick={() => onNavigate("library")}>◀ library</button>
  </div>

  {#if !selected}
    <div class="banner">no job selected · pick a run that has jobs.</div>
  {/if}

  <div class="split">
    <section class="left">
      <div class="io">
        <div class="tab-row noborder">
          <button class="tab" class:dim={io !== "input"} class:active={io === "input"} onclick={() => (io = "input")}>input</button>
          <button class="tab" class:active={io === "output"} class:dim={io !== "output"} onclick={() => (io = "output")}>output</button>
          <span class="hint">input.value · output.values</span>
        </div>
      </div>
      <div class="search">
        <input class="field" placeholder="search this run’s jobs…" bind:value={q} />
      </div>
      <div class="scroll">
        <table class="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>{io === "input" ? "input.value" : "title / output"}</th>
              <th>tmdb</th>
              <th>task</th>
            </tr>
          </thead>
          <tbody>
            {#each filtered as it}
              <tr
                class="clickable"
                class:sel={it.id === selected?.id}
                onclick={() => onNavigate("item", { jobId: it.id })}
              >
                <td>{it.index}</td>
                <td>
                  {#if io === "input"}
                    {it.path || "—"}
                  {:else}
                    {it.title}
                    {#if (it.output?.values || []).length}
                      <div class="muted tiny">{it.output.values.join(" · ")}</div>
                    {/if}
                  {/if}
                </td>
                <td class="c {markClass(it.marks?.tmdb)}">{mark(it.marks?.tmdb || "no")}</td>
                <td class="c {markClass(it.marks?.tasker)}">{mark(it.marks?.tasker || "no")}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="foot">
        <span>{filtered.length} jobs · {selected?.id || "—"}</span>
        <span>outputs · {outputs.length}</span>
      </div>
    </section>

    <section class="right">
      <div class="prow">
        <span class="label">plugin</span>
        <div class="tab-row noborder wrap">
          {#each pluginTabs as name}
            <button
              class="tab"
              class:active={plugin === name}
              class:dim={plugin !== name && name !== "all"}
              onclick={() => (plugin = name)}
            >
              {name}
              {#if name !== "all" && stageOf(name, snap.plugins)}
                <span class="bdg {stageOf(name, snap.plugins)}">{stageOf(name, snap.plugins)[0]}</span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
      <div class="cats">
        <span class="label">category · hardcoded slots</span>
        {#each CATEGORIES as c}
          <button class="btn mini" class:active={category === c} onclick={() => (category = c)}>{c}</button>
        {/each}
      </div>

      <div class="content">
        <div class="art">
          <div class="ph solid poster">no artwork url in job payload</div>
          <div class="muted cap">poster field not resolved by API</div>
        </div>

        <div class="body">
          {#if !selected}
            <div class="muted">empty</div>
          {:else if category === "general"}
            <div class="title">{general.title}</div>
            <div class="muted tiny">{selected.id} · {selected.path}</div>
            <div class="kv-2 mt">
              <span class="k">year</span><span>{general.year}</span>
              <span class="k">imdb id</span><span>{general.imdb}</span>
              <span class="k">release date</span><span>{general.release}</span>
              <span class="k">tmdb id</span><span>{general.tmdb}</span>
              <span class="k">certification</span><span>{general.cert}</span>
              <span class="k">runtime</span><span>{general.runtime}</span>
              <span class="k">genres</span><span>{general.genres}</span>
              <span class="k">production</span><span>{general.production}</span>
              <span class="k">country</span><span>{general.country}</span>
              <span class="k">spoken langs</span><span>{general.langs}</span>
            </div>
            <div class="rating">
              <b>{general.rating}</b>
              <span class="muted tiny">{general.votes} votes</span>
            </div>
            <div class="label mt">tagline</div>
            <div>{general.tagline || "—"}</div>
            <div class="label mt">plot</div>
            <div class="plot">{general.plot || "—"}</div>
          {:else if category === "other"}
            <div class="label">top-level keys in current tab</div>
            {#each otherKeys as k}
              <div class="muted">{k}</div>
            {:else}
              <div class="muted">none</div>
            {/each}
          {:else}
            <div class="label">{category} · raw payload</div>
            <pre class="dump">{dump(inspected)}</pre>
          {/if}
        </div>

        <aside class="insp">
          <div class="label">source</div>
          <div class="muted tiny">
            {#if plugin === "all" && envelope}
              run.data[{selected?.index ?? 0}] · core envelope
            {:else if plugin === "all"}
              merged in ui · run.data empty on this run
            {:else}
              job.plugins.{plugin}
            {/if}
          </div>
          <div class="box">
            {#if envelope}
              All tab is the priority-resolved envelope from GET /runs.
            {:else}
              fallback merge · tmdb &gt; omdb &gt; tvdb &gt; tvmaze
            {/if}
          </div>
          <div class="label mt">pipeline keys</div>
          <div class="pipe">
            {#each pipeline as p}<span class="pill">{p}</span>{/each}
            {#if !pipeline.length}<span class="muted">no plugin payloads</span>{/if}
          </div>
        </aside>
      </div>
    </section>
  </div>
</div>

<style>
  .banner { padding: 8px 12px; background: var(--paper-3); border-bottom: 1px solid var(--ink); font-size: 11px; }
  .split { flex: 1; display: flex; min-height: 0; overflow: hidden; }
  .left { width: 42%; border-right: 1.5px solid var(--ink); display: flex; flex-direction: column; min-width: 0; }
  .right { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .io { padding: 8px 10px 0; background: var(--paper-2); border-bottom: 1.5px solid var(--ink); }
  .noborder { border: none; }
  .hint { margin-left: auto; font-size: 11px; color: var(--muted); align-self: center; padding-bottom: 6px; }
  .search, .prow, .cats {
    padding: 8px 10px;
    border-bottom: 1.5px solid var(--ink);
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .prow { background: var(--paper-2); }
  .wrap { flex-wrap: wrap; }
  .foot {
    border-top: 1.5px solid var(--ink);
    padding: 6px 12px;
    background: var(--paper-2);
    font-size: 11px;
    display: flex;
    justify-content: space-between;
  }
  .content { flex: 1; display: flex; overflow: hidden; min-height: 0; }
  .art { width: 160px; padding: 14px; border-right: 1px solid var(--line-2); }
  .poster { height: 200px; }
  .cap { font-size: 11px; margin-top: 4px; }
  .body { flex: 1; padding: 18px; overflow: auto; }
  .title { font-size: 24px; font-weight: 700; line-height: 1; }
  .tiny { font-size: 11px; }
  .mt { margin-top: 14px; }
  .rating { margin-top: 14px; display: flex; gap: 10px; align-items: center; }
  .plot { line-height: 1.55; max-width: 680px; }
  .dump { font-size: 11px; white-space: pre-wrap; background: var(--paper-2); border: 1px solid var(--ink); padding: 8px; }
  .insp { width: 240px; border-left: 1px solid var(--line-2); padding: 14px; background: var(--paper-2); overflow: auto; }
  .box { margin-top: 8px; border: 1px solid var(--ink); background: var(--paper); padding: 8px; font-size: 11px; line-height: 1.7; }
  .pipe { margin-top: 6px; line-height: 1.9; }
</style>
