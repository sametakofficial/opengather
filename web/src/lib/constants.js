export const NAV = [
  { id: "dashboard", icon: "◆", label: "dashboard" },
  { id: "library", icon: "▤", label: "library" },
  { id: "item", icon: "▣", label: "item detail" },
  { id: "runs", icon: "▶", label: "runs" },
  { id: "plugins", icon: "⚙", label: "plugins" },
  { id: "config", icon: "≡", label: "config" },
  { id: "playground", icon: "✦", label: "playground" },
  { id: "diagnostics", icon: "?", label: "diagnostics" },
];

export const CATEGORIES = [
  "general",
  "credentials",
  "media",
  "artwork",
  "trailer",
  "cast & crew",
  "ratings",
  "other",
];

/** Client-side All-tab merge. Not core data_priority. First wins. */
export const MERGE_ORDER = ["tmdb", "omdb", "tvdb", "tvmaze"];

export const PAGE_SIZE = 100;
export const RUN_TIMEOUT_MS = 5 * 60 * 1000;
