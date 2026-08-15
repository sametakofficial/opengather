const API = "/api/v1";

export class ApiError extends Error {
  constructor(status, path, body) {
    super(`${status} ${path}${body ? ` · ${body.slice(0, 240)}` : ""}`);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
    this.body = body;
  }
}

async function request(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, path, body);
  }
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}

export const api = {
  getHealth: () => request("/system/health"),
  getStatus: () => request("/system/status"),
  getVersion: () => request("/system/version"),

  listRuns: (page = 1, pageSize = 20) =>
    request(`/runs?page=${page}&page_size=${pageSize}`),

  getRun: (id) => request(`/runs/${encodeURIComponent(id)}`),

  getRunStatus: (id) => request(`/runs/${encodeURIComponent(id)}/status`),

  listJobs: ({ run_id, page = 1, page_size = 100 } = {}) => {
    const q = new URLSearchParams({
      page: String(page),
      page_size: String(page_size),
    });
    if (run_id) q.set("run_id", run_id);
    return request(`/jobs?${q}`);
  },

  getJob: (id) => request(`/jobs/${encodeURIComponent(id)}`),

  getJobPlugins: (id) =>
    request(`/jobs/${encodeURIComponent(id)}/plugins`),

  listPlugins: () => request("/plugins"),

  createRun: ({ dry_run = true, config } = {}, { signal } = {}) => {
    const body = { dry_run };
    if (config != null) body.config = config;
    return request("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  },
};

export function wantMock() {
  try {
    return new URLSearchParams(window.location.search).get("mock") === "1";
  } catch {
    return false;
  }
}
