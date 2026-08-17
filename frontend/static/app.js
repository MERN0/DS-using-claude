// Dashboard logic: loads reference data from /api/config, then drives the
// four panels (memory / skills / subagents / generate) purely through the
// REST endpoints in app.py. No server-side conversation state -- every
// request below carries `currentClient` itself.
//
// Each panel shows two layers on purpose: what's already active for every
// client (baseline memory rules, baseline skill bodies, the six built-in
// subagents -- all read-only reference, fetched once and/or per skill) and
// what this specific client adds on top (editable). Before this, the UI
// only ever showed the second layer, which is empty for a fresh client and
// easy to mistake for "nothing is configured yet".

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

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
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
      if (!config.clients.includes(name)) {
        config.clients.push(name);
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        clientSelect.appendChild(opt);
      }
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

  // Client-independent reference data: fetched once, never changes per client.
  $("baselineMemoryText").textContent = config.baseline_memory || "(no baseline rules file found)";
  renderBuiltInSubagents();

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
    wrap.className = "form-check chip-check";
    wrap.title = desc;
    wrap.innerHTML = `
      <input class="form-check-input" type="checkbox" value="${name}" id="${prefix}-${name}">
      <label class="form-check-label" for="${prefix}-${name}">${name}</label>`;
    container.appendChild(wrap);
  }
}

function selectClient(name) {
  currentClient = name;
  clientSelectSync(name);
  $("newClientName").value = "";
  setStatus("clientStatus", `Working on "${name}".`, "muted");
  $("workArea").classList.remove("d-none");
  loadMemory();
  renderSkillGallery();
  clearSkillForm();
  loadSubagents();
  updateGenerateReadiness();
}

function clientSelectSync(name) {
  const select = $("clientSelect");
  if (![...select.options].some((o) => o.value === name)) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }
  select.value = name;
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
  $("toggleBaselineMemoryBtn").addEventListener("click", () => {
    const box = $("baselineMemoryText");
    const btn = $("toggleBaselineMemoryBtn");
    const nowHidden = box.classList.toggle("d-none");
    btn.innerHTML = nowHidden
      ? '<i class="bi bi-eye"></i> Show baseline rules'
      : '<i class="bi bi-eye-slash"></i> Hide baseline rules';
  });
}

async function loadMemory() {
  const data = await api("GET", `/api/clients/${currentClient}/memory`);
  $("memoryText").value = data.text;
  setStatus("memoryStatus", data.text ? "This client has its own addition below." : "No addition yet -- baseline rules only.", "muted");
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
      renderSkillGallery();
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
  document.querySelector('.nav-link[data-tab="skills"]').scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function renderSkillGallery() {
  const overrides = await api("GET", `/api/clients/${currentClient}/skills`); // [{name, description}]
  const overrideByName = Object.fromEntries(overrides.map((o) => [o.name, o.description]));

  const gallery = $("skillGallery");
  gallery.innerHTML = "";
  for (const [name, baseDesc] of Object.entries(config.skills)) {
    const isCustom = Object.prototype.hasOwnProperty.call(overrideByName, name);
    const row = document.createElement("div");
    row.className = "skill-card";
    row.innerHTML = `
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
        <div>
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <strong>${escapeHtml(name)}</strong>
            <span class="badge ${isCustom ? "text-bg-success" : "text-bg-secondary"} fw-normal">
              ${isCustom ? "Custom override" : "Baseline"}
            </span>
          </div>
          <div class="text-muted small">${escapeHtml(isCustom ? overrideByName[name] : baseDesc)}</div>
        </div>
        <div class="d-flex gap-2 flex-wrap align-items-center">
          ${name === "domain-knowledge" ? `
            <select class="form-select form-select-sm skill-baseline-domain" style="max-width:190px;" data-skill="${name}">
              <option value="">Baseline for domain&hellip;</option>
              ${config.domains.map((d) => `<option value="${d.key}">${escapeHtml(d.label)}</option>`).join("")}
            </select>` : `
            <button class="btn btn-sm btn-outline-secondary" data-baseline="${name}">
              <i class="bi bi-eye"></i> View baseline</button>`}
          <button class="btn btn-sm btn-outline-primary" data-edit="${name}">
            <i class="bi bi-pencil"></i> ${isCustom ? "Edit" : "Override"}</button>
          ${isCustom ? `<button class="btn btn-sm btn-outline-danger" data-delete="${name}"><i class="bi bi-trash"></i></button>` : ""}
        </div>
      </div>
      <pre class="baseline-box mt-2 d-none" data-baseline-box="${name}"></pre>`;
    gallery.appendChild(row);
  }

  gallery.querySelectorAll("[data-baseline]").forEach((btn) =>
    btn.addEventListener("click", () => toggleSkillBaseline(btn.dataset.baseline))
  );
  gallery.querySelectorAll(".skill-baseline-domain").forEach((sel) =>
    sel.addEventListener("change", () => {
      if (sel.value) showSkillBaseline(sel.dataset.skill, sel.value);
    })
  );
  gallery.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      $("skillNameSelect").value = btn.dataset.edit;
      await onSkillPicked();
    })
  );
  gallery.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api("DELETE", `/api/clients/${currentClient}/skills/${btn.dataset.delete}`);
      renderSkillGallery();
    })
  );
}

async function toggleSkillBaseline(name, baseDomain) {
  const box = document.querySelector(`[data-baseline-box="${name}"]`);
  if (!box.classList.contains("d-none") && !baseDomain) {
    box.classList.add("d-none");
    return;
  }
  await showSkillBaseline(name, baseDomain);
}

async function showSkillBaseline(name, baseDomain) {
  const box = document.querySelector(`[data-baseline-box="${name}"]`);
  const qs = baseDomain ? `?base_domain=${encodeURIComponent(baseDomain)}` : "";
  const data = await api("GET", `/api/skills/${name}/baseline${qs}`);
  box.textContent = data.body || "(nothing to show yet)";
  box.classList.remove("d-none");
}

// ---------------------------------------------------------------------------
// Subagents
// ---------------------------------------------------------------------------

function renderBuiltInSubagents() {
  const list = $("builtInSubagentList");
  list.innerHTML = "";
  (config.built_in_subagents || []).forEach((s, i) => {
    const row = document.createElement("div");
    row.className = "built-in-subagent-card";
    row.innerHTML = `
      <span class="step-badge step-badge-sm">${i + 1}</span>
      <div>
        <strong>${escapeHtml(s.name)}</strong>
        <div class="text-muted small">${escapeHtml(s.description)}</div>
      </div>`;
    list.appendChild(row);
  });
}

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
      <div><strong>${escapeHtml(item.name)}</strong><div class="text-muted small">${escapeHtml(item.description)}</div></div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-secondary" data-edit="${item.name}">
          <i class="bi bi-pencil"></i> Edit</button>
        <button class="btn btn-sm btn-outline-danger" data-delete="${item.name}">
          <i class="bi bi-trash"></i></button>
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
  $("genSpinner").classList.remove("d-none");
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
    $("genSpinner").classList.add("d-none");
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
      setStatus("genStatus", "Running... this can take several minutes.", "muted");
      return;
    }
    clearInterval(pollTimer);
    $("genSpinner").classList.add("d-none");
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
