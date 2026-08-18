// Thin fetch wrapper for the FastAPI backend (see ../app.py). No client-side
// state beyond what each call needs -- the backend is a stateless REST API
// except for the single generation job slot.
//
// Every exported function takes an optional trailing `{ signal }` so a
// caller can cancel a request (e.g. via AbortController) when it's no
// longer relevant -- switching clients quickly while a fetch is still in
// flight would otherwise let a stale response overwrite newer state. A
// caller that doesn't pass a signal behaves exactly as before.

class ApiError extends Error {}

async function request(method, url, body, { signal } = {}) {
  const opts = { method, headers: {}, signal };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    throw new ApiError((data && data.detail) || `Request failed (${res.status})`);
  }
  return data;
}

const enc = encodeURIComponent;

export const api = {
  getConfig: (opts) => request("GET", "/api/config", undefined, opts),
  setMcpEnabled: (enabled, opts) => request("PUT", "/api/mcp", { enabled }, opts),

  createClient: (name, opts) => request("POST", "/api/clients", { name }, opts),

  getMemory: (client, opts) => request("GET", `/api/clients/${enc(client)}/memory`, undefined, opts),
  putMemory: (client, text, opts) => request("PUT", `/api/clients/${enc(client)}/memory`, { text }, opts),
  deleteMemory: (client, opts) => request("DELETE", `/api/clients/${enc(client)}/memory`, undefined, opts),

  listSkills: (client, opts) => request("GET", `/api/clients/${enc(client)}/skills`, undefined, opts),
  getSkill: (client, name, baseDomain, opts) =>
    request(
      "GET",
      `/api/clients/${enc(client)}/skills/${enc(name)}${baseDomain ? `?base_domain=${enc(baseDomain)}` : ""}`,
      undefined,
      opts
    ),
  putSkill: (client, name, description, body, opts) =>
    request("PUT", `/api/clients/${enc(client)}/skills/${enc(name)}`, { description, body }, opts),
  deleteSkill: (client, name, opts) =>
    request("DELETE", `/api/clients/${enc(client)}/skills/${enc(name)}`, undefined, opts),
  getSkillBaseline: (name, baseDomain, opts) =>
    request(
      "GET",
      `/api/skills/${enc(name)}/baseline${baseDomain ? `?base_domain=${enc(baseDomain)}` : ""}`,
      undefined,
      opts
    ),

  listSubagents: (client, opts) => request("GET", `/api/clients/${enc(client)}/subagents`, undefined, opts),
  getSubagent: (client, name, opts) =>
    request("GET", `/api/clients/${enc(client)}/subagents/${enc(name)}`, undefined, opts),
  putSubagent: (client, name, payload, opts) =>
    request("PUT", `/api/clients/${enc(client)}/subagents/${enc(name)}`, payload, opts),
  deleteSubagent: (client, name, opts) =>
    request("DELETE", `/api/clients/${enc(client)}/subagents/${enc(name)}`, undefined, opts),

  upload: async (files, { signal } = {}) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await fetch("/api/upload", { method: "POST", body: form, signal });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.detail || "Upload failed.");
    return data;
  },

  generate: (payload, opts) => request("POST", "/api/generate", payload, opts),
  generateStatus: (since, opts) => request("GET", `/api/generate/status?since=${since}`, undefined, opts),
  downloadUrl: () => "/api/generate/download",

  // Read-only views over the current run's workspace (see
  // ../workspace_reader.py) -- all scoped to whatever generation is
  // current/most-recent, 404ing before any run has produced one yet.
  workspaceManifest: (opts) => request("GET", "/api/generate/workspace", undefined, opts),
  workspaceClusters: (opts) => request("GET", "/api/generate/workspace/clusters", undefined, opts),
  workspaceRequirements: (clusterId, opts) =>
    request(
      "GET",
      `/api/generate/workspace/requirements${clusterId ? `?cluster_id=${enc(clusterId)}` : ""}`,
      undefined,
      opts
    ),
  workspaceTestcases: (opts) => request("GET", "/api/generate/workspace/testcases", undefined, opts),
  workspaceResolved: (clusterId, opts) =>
    request("GET", `/api/generate/workspace/resolved/${enc(clusterId)}`, undefined, opts),
  workspaceQaReport: (opts) => request("GET", "/api/generate/workspace/qa_report", undefined, opts),
  workspaceSummary: (opts) => request("GET", "/api/generate/workspace/summary", undefined, opts),
};

export { ApiError };
