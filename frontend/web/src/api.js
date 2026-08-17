// Thin fetch wrapper for the FastAPI backend (see ../app.py). No client-side
// state beyond what each call needs -- the backend is a stateless REST API
// except for the single generation job slot.

class ApiError extends Error {}

async function request(method, url, body) {
  const opts = { method, headers: {} };
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
  getConfig: () => request("GET", "/api/config"),

  createClient: (name) => request("POST", "/api/clients", { name }),

  getMemory: (client) => request("GET", `/api/clients/${enc(client)}/memory`),
  putMemory: (client, text) => request("PUT", `/api/clients/${enc(client)}/memory`, { text }),
  deleteMemory: (client) => request("DELETE", `/api/clients/${enc(client)}/memory`),

  listSkills: (client) => request("GET", `/api/clients/${enc(client)}/skills`),
  getSkill: (client, name, baseDomain) =>
    request(
      "GET",
      `/api/clients/${enc(client)}/skills/${enc(name)}${baseDomain ? `?base_domain=${enc(baseDomain)}` : ""}`
    ),
  putSkill: (client, name, description, body) =>
    request("PUT", `/api/clients/${enc(client)}/skills/${enc(name)}`, { description, body }),
  deleteSkill: (client, name) => request("DELETE", `/api/clients/${enc(client)}/skills/${enc(name)}`),
  getSkillBaseline: (name, baseDomain) =>
    request("GET", `/api/skills/${enc(name)}/baseline${baseDomain ? `?base_domain=${enc(baseDomain)}` : ""}`),

  listSubagents: (client) => request("GET", `/api/clients/${enc(client)}/subagents`),
  getSubagent: (client, name) => request("GET", `/api/clients/${enc(client)}/subagents/${enc(name)}`),
  putSubagent: (client, name, payload) =>
    request("PUT", `/api/clients/${enc(client)}/subagents/${enc(name)}`, payload),
  deleteSubagent: (client, name) => request("DELETE", `/api/clients/${enc(client)}/subagents/${enc(name)}`),

  upload: async (files) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data.detail || "Upload failed.");
    return data;
  },

  generate: (payload) => request("POST", "/api/generate", payload),
  generateStatus: (since) => request("GET", `/api/generate/status?since=${since}`),
  downloadUrl: () => "/api/generate/download",
};

export { ApiError };
