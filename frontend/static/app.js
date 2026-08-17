// Dashboard logic: loads reference data from /api/config, then drives the
// four panels (memory / skills / subagents / generate) purely through the
// REST endpoints in app.py. No server-side conversation state -- every
// request below carries `currentClient` itself.

let config = null;
let currentClient = null;
let uploadId = null;
let pollTimer = null;

const $ = (id) => document.getElementById(id);

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }
  if (!res.ok) {
    const msg = (data && data.detail) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

function setStatus(id, text, kind) {
  const el = $(id);
  el.textContent = text;
  el.className = "small mt-2" + (kind ? ` text-${kind}` : "");
}

// ---------------------------------------------------------------------------
// Boot / client selection
// ---------------------------------------------------------------------------

async function boot() {
  config = await api("GET", "/api/config");

  const clientSelect = $("clientSelect");
  for (const name of config.clients) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    clientSelect.appendChild(opt);
  }
  clientSelect.addEventListener("change", () => {
    if (clientSelect.value) selectClient(clientSelect.value);
  });

  $("createClientBtn").addEventListener("click", async () => {
    const name = $("newClientName").value.trim();
    if (!name) return;
    try {
      await api("POST", "/api/clients", { name });
      selectClient(name);
    } catch (e) {
      setStatus("clientStatus", e.message, "danger");
    }
  });

  populateSelect($("skillNameSelect"), Object.keys(config.skills), (name) => name);
  $("skillNameSelect").addEventListener("change", onSkillPicked);
  populateSelect($("skillBaseDomain"), config.domains.map((d) => d.key), (k) =>
    (config.domains.find((d) => d.key === k) || {}).label || k
  );
  $("skillBaseDomain").addEventListener("change", onSkillPicked);

  populateSelect($("genDomain"), config.domains.map((d) => d.key), (k) =>
    (config.domains.find((d) => d.key === k) || {}).label || k
  );
  populateSelect($("genFormat"), config.output_formats, (f) => f);

  renderCheckboxGroup($("subagentTools"), "tool", config.tools);
  renderCheckboxGroup($("subagentSkills"), "skill", config.skills);

  setupTabs();
  setupMemory();
  setupSkills();
  setupSubagents();
  setupGenerate();
}

function populateSelect(select, values, labelFor) {
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = labelFor(v);
    select.appendChild(opt);
  }
}

function renderCheckboxGroup(container, prefix, itemsWithDescriptions) {
  container.innerHTML = "";
  for (const [name, desc] of Object.entries(itemsWithDescriptions)) {
    const wrap = document.createElement("div");
    wrap.className = "form-check";
    wrap.title = desc;
    wrap.innerHTML = `
      <input class="form-check-input" type="checkbox" value="${name}" id="${prefix}-${name}">
      <label class="form-check-label" for="${prefix}-${name}">${name}</label>`;
    container.appendChild(wrap);
  }
}

function selectClient(name) {
  currentClient = name;
  $("clientSelect").value = config.clients.includes(name) ? name : "";
  $("newClientName").value = "";
  setStatus("clientStatus", `Working on "${name}".`, "muted");
  $("workArea").classList.remove("d-none");
  loadMemory();
  loadSkills();
  loadSubagents();
  updateGenerateReadiness();
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function setupTabs() {
  const buttons = document.querySelectorAll(".nav-link[data-tab]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("d-none"));
      document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).classList.remove("d-none");
    });
  });
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

function setupMemory() {
  $("saveMemoryBtn").addEventListener("click", async () => {
    try {
      await api("PUT", `/api/clients/${currentClient}/memory`, { text: $("memoryText").value });
      setStatus("memoryStatus", "Saved.", "success");
    } catch (e) {
      setStatus("memoryStatus", e.message, "danger");
    }
  });
  $("deleteMemoryBtn").addEventListener("click", async () => {
    await api("DELETE", `/api/clients/${currentClient}/memory`);
    $("memoryText").value = "";
    setStatus("memoryStatus", "Deleted.", "muted");
  });
}

async function loadMemory() {
  const data = await api("GET", `/api/clients/${currentClient}/memory`);
  $("memoryText").value = data.text;
  setStatus("memoryStatus", "", "");
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

function setupSkills() {
  $("saveSkillBtn").addEventListener("click", async () => {
    const name = $("skillNameSelect").value;
    if (!name) return setStatus("skillStatus", "Pick a skill first.", "danger");
    try {
      await api("PUT", `/api/clients/${currentClient}/skills/${name}`, {
        description: $("skillDescription").value,
        body: $("skillBody").value,
      });
      setStatus("skillStatus", `Saved "${name}".`, "success");
      loadSkills();
    } catch (e) {
      setStatus("skillStatus", e.message, "danger");
    }
  });
  $("clearSkillFormBtn").addEventListener("click", clearSkillForm);
}

function clearSkillForm() {
  $("skillNameSelect").value = "";
  $("skillBaseDomain").value = "";
  $("skillDomainWrap").classList.add("d-none");
  $("skillDescription").value = "";
  $("skillBody").value = "";
  $("skillHint").textContent = "";
  setStatus("skillStatus", "", "");
}

async function onSkillPicked() {
  const name = $("skillNameSelect").value;
  if (!name) return;
  $("skillHint").textContent = config.skills[name] || "";
  $("skillDomainWrap").classList.toggle("d-none", name !== "domain-knowledge");
  if (name === "domain-knowledge" && !$("skillBaseDomain").value) {
    $("skillDescription").value = "";
    $("skillBody").value = "";
    return;
  }
  const baseDomain = $("skillBaseDomain").value;
  const qs = baseDomain ? `?base_domain=${encodeURIComponent(baseDomain)}` : "";
  const data = await api("GET", `/api/clients/${currentClient}/skills/${name}${qs}`);
  $("skillDescription").value = data.description;
  $("skillBody").value = data.body;
}

async function loadSkills() {
  const items = await api("GET", `/api/clients/${currentClient}/skills`);
  const list = $("skillList");
  list.innerHTML = "";
  $("skillListEmpty").classList.toggle("d-none", items.length > 0);
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "list-group-item d-flex justify-content-between align-items-center";
    row.innerHTML = `
      <div><strong>${item.name}</strong><div class="text-muted small">${item.description}</div></div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-secondary" data-edit="${item.name}">Edit</button>
        <button class="btn btn-sm btn-outline-danger" data-delete="${item.name}">Delete</button>
      </div>`;
    list.appendChild(row);
  }
  list.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      $("skillNameSelect").value = btn.dataset.edit;
      await onSkillPicked();
    })
  );
  list.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api("DELETE", `/api/clients/${currentClient}/skills/${btn.dataset.delete}`);
      loadSkills();
    })
  );
}

// ---------------------------------------------------------------------------
// Subagents
// ---------------------------------------------------------------------------

function setupSubagents() {
  $("saveSubagentBtn").addEventListener("click", async () => {
    const name = $("subagentName").value.trim();
    if (!name) return setStatus("subagentStatus", "Needs a name.", "danger");
    const tools = [...document.querySelectorAll('#subagentTools input:checked')].map((i) => i.value);
    const skills = [...document.querySelectorAll('#subagentSkills input:checked')].map((i) => i.value);
    try {
      await api("PUT", `/api/clients/${currentClient}/subagents/${name}`, {
        description: $("subagentDescription").value,
        prompt_body: $("subagentPrompt").value,
        tools,
        skills,
      });
      setStatus("subagentStatus", `Saved "${name}".`, "success");
      loadSubagents();
    } catch (e) {
      setStatus("subagentStatus", e.message, "danger");
    }
  });
  $("clearSubagentFormBtn").addEventListener("click", clearSubagentForm);
}

function clearSubagentForm() {
  $("subagentName").value = "";
  $("subagentName").disabled = false;
  $("subagentDescription").value = "";
  $("subagentPrompt").value = "";
  document.querySelectorAll('#subagentTools input, #subagentSkills input').forEach((i) => (i.checked = false));
  setStatus("subagentStatus", "", "");
}

async function editSubagent(name) {
  const data = await api("GET", `/api/clients/${currentClient}/subagents/${name}`);
  $("subagentName").value = name;
  $("subagentName").disabled = true; // renaming = a different file; keep this simple
  $("subagentDescription").value = data.description;
  $("subagentPrompt").value = data.prompt_body;
  document.querySelectorAll('#subagentTools input').forEach((i) => (i.checked = data.tools.includes(i.value)));
  document.querySelectorAll('#subagentSkills input').forEach((i) => (i.checked = data.skills.includes(i.value)));
}

async function loadSubagents() {
  const items = await api("GET", `/api/clients/${currentClient}/subagents`);
  const list = $("subagentList");
  list.innerHTML = "";
  $("subagentListEmpty").classList.toggle("d-none", items.length > 0);
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "list-group-item d-flex justify-content-between align-items-center";
    row.innerHTML = `
      <div><strong>${item.name}</strong><div class="text-muted small">${item.description}</div></div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-secondary" data-edit="${item.name}">Edit</button>
        <button class="btn btn-sm btn-outline-danger" data-delete="${item.name}">Delete</button>
      </div>`;
    list.appendChild(row);
  }
  list.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => editSubagent(btn.dataset.edit))
  );
  list.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api("DELETE", `/api/clients/${currentClient}/subagents/${btn.dataset.delete}`);
      loadSubagents();
    })
  );
}

// ---------------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------------

function setupGenerate() {
  $("uploadBtn").addEventListener("click", async () => {
    const files = $("genFiles").files;
    if (!files.length) return setStatus("uploadStatus", "Choose files first.", "danger");
    const form = new FormData();
    for (const f of files) form.append("files", f);
    setStatus("uploadStatus", "Uploading...", "muted");
    try {
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed.");
      uploadId = data.upload_id;
      setStatus("uploadStatus", `Uploaded ${data.files.length} file(s).`, "success");
      const select = $("reqFileSelect");
      select.innerHTML = "";
      for (const name of data.files) {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        select.appendChild(opt);
      }
      $("reqFileWrap").classList.remove("d-none");
      updateGenerateReadiness();
    } catch (e) {
      setStatus("uploadStatus", e.message, "danger");
    }
  });

  $("generateBtn").addEventListener("click", startGenerate);
  ["genVersion", "genUsername"].forEach((id) => $(id).addEventListener("input", updateGenerateReadiness));
}

function updateGenerateReadiness() {
  const ready = !!(currentClient && uploadId && $("genVersion").value.trim() && $("genUsername").value.trim());
  $("generateBtn").disabled = !ready;
}

async function startGenerate() {
  $("generateBtn").disabled = true;
  $("downloadBtn").classList.add("d-none");
  $("genLog").classList.remove("d-none");
  $("genLog").textContent = "";
  setStatus("genStatus", "Starting...", "muted");

  try {
    await api("POST", "/api/generate", {
      client: currentClient,
      domain: $("genDomain").value,
      output_format: $("genFormat").value,
      username: $("genUsername").value,
      current_version: $("genVersion").value,
      upload_id: uploadId,
      requirement_filename: $("reqFileSelect").value,
    });
  } catch (e) {
    setStatus("genStatus", e.message, "danger");
    updateGenerateReadiness();
    return;
  }

  let since = 0;
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const status = await api("GET", `/api/generate/status?since=${since}`);
    since = status.log_total;
    if (status.log.length) {
      const atBottom = $("genLog").scrollHeight - $("genLog").scrollTop <= $("genLog").clientHeight + 20;
      $("genLog").textContent += status.log.join("\n") + "\n";
      if (atBottom) $("genLog").scrollTop = $("genLog").scrollHeight;
    }
    if (status.status === "running") {
      setStatus("genStatus", "Running...", "muted");
      return;
    }
    clearInterval(pollTimer);
    if (status.status === "done") {
      setStatus("genStatus", "Done -- workbook ready to download.", "success");
      $("downloadBtn").classList.remove("d-none");
    } else {
      setStatus("genStatus", status.error || "Generation failed.", "danger");
    }
    updateGenerateReadiness();
  }, 1500);
}

boot();
