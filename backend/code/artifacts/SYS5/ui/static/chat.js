// Drives the chat UI: renders bot turns, renders whatever input widget the
// current step calls for (buttons / checkboxes / text / textarea), and
// posts the user's reply back to /api/chat. The server (state.py) is the
// only thing that knows what step comes next -- this file has no
// knowledge of the conversation's shape at all, it just renders whatever
// it's told.

const chatEl = document.getElementById("chat");
const composer = document.getElementById("composer");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");

let busy = false;

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Deliberately tiny: the server only ever sends **bold**, `code`, fenced
// ```code blocks```, and "- " bullet lines -- see state.py's bot() calls.
// No need for a real Markdown library for that small a surface.
function renderMarkdownLite(text) {
  const fenceParts = text.split(/```/);
  let html = "";
  fenceParts.forEach((part, i) => {
    if (i % 2 === 1) {
      html += `<pre class="chat-code">${escapeHtml(part.trim())}</pre>`;
      return;
    }
    const lines = escapeHtml(part).split("\n");
    let inList = false;
    let out = "";
    for (const line of lines) {
      const bullet = line.match(/^- (.*)$/);
      if (bullet) {
        if (!inList) {
          out += "<ul>";
          inList = true;
        }
        out += `<li>${bullet[1]}</li>`;
      } else {
        if (inList) {
          out += "</ul>";
          inList = false;
        }
        if (line.trim() === "") {
          out += "<br>";
        } else {
          out += `<p class="mb-1">${line}</p>`;
        }
      }
    }
    if (inList) out += "</ul>";
    html += out;
  });
  return html
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function addBubble(text, who) {
  const wrap = document.createElement("div");
  wrap.className = `d-flex ${who === "user" ? "justify-content-end" : "justify-content-start"}`;
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble chat-bubble-${who} p-3 rounded-3 shadow-sm`;
  if (who === "user") {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdownLite(text);
  }
  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  wrap.scrollIntoView({ behavior: "smooth", block: "end" });
}

function addBotTurn(turn) {
  for (const msg of turn.messages || []) {
    addBubble(msg, "bot");
  }
  renderInput(turn);
}

function clearInputArea() {
  const existing = document.getElementById("choiceArea");
  if (existing) existing.remove();
  textInput.classList.add("d-none");
  sendBtn.classList.add("d-none");
  textInput.value = "";
}

function renderInput(turn) {
  clearInputArea();
  const kind = turn.kind || "none";

  if (kind === "checkboxes") {
    renderCheckboxes(turn.choices || []);
    return;
  }

  if (kind === "buttons") {
    renderButtons(turn.choices || []);
    if (turn.placeholder) {
      showTextInput(turn.placeholder, turn.prefill || "", false);
    }
    return;
  }

  if (kind === "text") {
    showTextInput(turn.placeholder, turn.prefill || "", false);
    return;
  }

  if (kind === "textarea") {
    showTextInput(turn.placeholder, turn.prefill || "", true);
    return;
  }
  // kind === "none": nothing to show.
}

function renderButtons(choices) {
  if (!choices.length) return;
  const area = document.createElement("div");
  area.id = "choiceArea";
  area.className = "d-flex flex-wrap gap-2 mb-2";
  for (const choice of choices) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-outline-primary";
    btn.textContent = choice.label;
    btn.addEventListener("click", () => {
      addBubble(choice.label, "user");
      send({ value: choice.value });
    });
    area.appendChild(btn);
  }
  composer.prepend(area);
}

function renderCheckboxes(choices) {
  const area = document.createElement("div");
  area.id = "choiceArea";
  area.className = "d-flex flex-column gap-2 mb-2 p-2 border rounded-3 bg-light-subtle";
  for (const choice of choices) {
    const row = document.createElement("div");
    row.className = "form-check";
    const input = document.createElement("input");
    input.className = "form-check-input";
    input.type = "checkbox";
    input.id = `cb-${choice.value}`;
    input.checked = !!choice.checked;
    input.dataset.value = choice.value;
    const label = document.createElement("label");
    label.className = "form-check-label";
    label.setAttribute("for", input.id);
    label.textContent = choice.label;
    row.appendChild(input);
    row.appendChild(label);
    area.appendChild(row);
  }
  const doneBtn = document.createElement("button");
  doneBtn.type = "button";
  doneBtn.className = "btn btn-primary align-self-end";
  doneBtn.textContent = "Done";
  doneBtn.addEventListener("click", () => {
    const boxes = area.querySelectorAll("input[type=checkbox]");
    const selected = [...boxes].filter((b) => b.checked).map((b) => b.dataset.value);
    addBubble(selected.length ? selected.join(", ") : "(none selected)", "user");
    send({ selected });
  });
  area.appendChild(doneBtn);
  composer.prepend(area);
}

function showTextInput(placeholder, prefill, multiline) {
  textInput.classList.remove("d-none");
  sendBtn.classList.remove("d-none");
  textInput.placeholder = placeholder || "";
  textInput.value = prefill || "";
  textInput.rows = multiline ? 6 : 1;
  textInput.focus();
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = textInput.value.trim();
  if (!text || busy) return;
  addBubble(text, "user");
  send({ text });
});

async function send(payload) {
  if (busy) return;
  busy = true;
  clearInputArea();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      addBubble("Lost the connection to the server -- try refreshing the page.", "bot");
      return;
    }
    const turn = await res.json();
    addBotTurn(turn);
  } catch (err) {
    addBubble("Lost the connection to the server -- try refreshing the page.", "bot");
  } finally {
    busy = false;
  }
}

async function boot() {
  const res = await fetch("/api/start", { method: "POST" });
  const turn = await res.json();
  addBotTurn(turn);
}

boot();
