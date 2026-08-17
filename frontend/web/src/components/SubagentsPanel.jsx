import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Users, Bot, UserPlus, Pencil, Trash2, Save, X } from "lucide-react";
import { Card, CardBody, SectionTitle, Button, Input, Textarea, Spinner } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";

const EMPTY_FORM = { name: "", description: "", prompt_body: "", tools: [], skills: [] };

// Mirrors settings.validate_kebab_name(..., require_suffix="-agent")
// server-side -- UX aid only, the backend re-validates and is the actual
// authority (builders.py's validate_subagent_name). The "-agent" suffix
// matches the six built-in subagents' own naming (discovery-agent,
// qa-validation-agent, ...) so a custom one reads identically in logs and
// can never collide with a built-in name.
const KEBAB_AGENT_RE = /^[a-z0-9]+(-[a-z0-9]+)*-agent$/;

function nameHint(name) {
  if (!name) return null;
  if (name.length < 2 || name.length > 64) return "2-64 characters.";
  if (!KEBAB_AGENT_RE.test(name)) {
    return 'Lowercase-with-hyphens, ending in "-agent", e.g. "extra-safety-checks-agent".';
  }
  return null;
}

export default function SubagentsPanel({ client, builtIn, tools, skills }) {
  const [custom, setCustom] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingExisting, setEditingExisting] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const nameError = editingExisting ? null : nameHint(form.name.trim());

  const refresh = () => api.listSubagents(client).then(setCustom);

  useEffect(() => {
    setCustom(null);
    setForm(EMPTY_FORM);
    setEditingExisting(false);
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  async function edit(name) {
    const data = await api.getSubagent(client, name);
    setForm({ name, ...data });
    setEditingExisting(true);
    document.getElementById("subagent-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function save() {
    if (!form.name.trim()) return toast("A subagent needs a name.", "error");
    if (nameError) return toast(nameError, "error");
    setBusy(true);
    try {
      await api.putSubagent(client, form.name.trim(), {
        description: form.description,
        prompt_body: form.prompt_body,
        tools: form.tools,
        skills: form.skills,
      });
      toast(`Saved "${form.name}".`, "success");
      setForm(EMPTY_FORM);
      setEditingExisting(false);
      refresh();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(name) {
    await api.deleteSubagent(client, name);
    toast(`Deleted "${name}".`, "info");
    refresh();
  }

  function toggle(field, value) {
    setForm((f) => {
      const set = new Set(f[field]);
      if (set.has(value)) {
        set.delete(value);
      } else {
        set.add(value);
      }
      return { ...f, [field]: [...set] };
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardBody>
          <SectionTitle icon={<Bot className="h-4 w-4 text-brand-600" />} badge="always included">
            Built-in subagents
          </SectionTitle>
          <p className="text-sm text-ink-500 mb-4">
            The six specialists every run already delegates to, in order. Custom subagents below are purely
            additive to these, never a replacement.
          </p>
          <div className="grid gap-2.5 sm:grid-cols-2">
            {builtIn.map((s, i) => (
              <div
                key={s.name}
                className="flex items-start gap-2.5 rounded-xl border border-ink-100 bg-ink-50/50 px-3.5 py-3"
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500 text-[11px] font-semibold text-white mt-0.5">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink-900">{s.name}</div>
                  <p className="text-xs text-ink-500 mt-0.5 line-clamp-3">{s.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <SectionTitle icon={<Users className="h-4 w-4 text-brand-600" />}>
            This project's custom subagents
          </SectionTitle>
          {custom === null ? (
            <div className="flex h-20 items-center justify-center text-ink-300">
              <Spinner className="h-5 w-5" />
            </div>
          ) : custom.length === 0 ? (
            <p className="text-sm text-ink-400 py-2">No custom subagents for this project yet.</p>
          ) : (
            <div className="flex flex-col gap-2">
              <AnimatePresence>
                {custom.map((s) => (
                  <motion.div
                    key={s.name}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex items-center justify-between gap-3 rounded-xl border border-ink-100 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink-900">{s.name}</div>
                      <p className="text-xs text-ink-500 line-clamp-1">{s.description}</p>
                    </div>
                    <div className="flex shrink-0 gap-1.5">
                      <Button
                        size="sm"
                        icon={<Pencil className="h-3.5 w-3.5" />}
                        onClick={() => edit(s.name)}
                      >
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        tone="danger"
                        icon={<Trash2 className="h-3.5 w-3.5" />}
                        onClick={() => remove(s.name)}
                      />
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </CardBody>
      </Card>

      <Card id="subagent-form">
        <CardBody>
          <SectionTitle icon={<UserPlus className="h-4 w-4 text-brand-600" />}>
            {editingExisting ? `Editing "${form.name}"` : "Add a subagent"}
          </SectionTitle>
          <p className="text-sm text-ink-500 mb-3">
            A specialist the orchestrator can delegate a job to, alongside the six above &mdash; purely
            additive, never a replacement for the standard pipeline.
          </p>
          <div className="mb-2.5">
            <Input
              value={form.name}
              disabled={editingExisting}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="name (lowercase-with-hyphens, e.g. extra-safety-checks-agent)"
              className={nameError ? "border-rose-300 focus:border-rose-400 focus:ring-rose-100" : ""}
            />
            {nameError && <p className="mt-1 text-xs text-rose-600">{nameError}</p>}
          </div>
          <Input
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="One or two sentences: what it does and when the orchestrator should call it."
            className="mb-2.5"
          />
          <Textarea
            rows={7}
            value={form.prompt_body}
            onChange={(e) => setForm((f) => ({ ...f, prompt_body: e.target.value }))}
            placeholder="Its system prompt -- its own instructions, as Markdown."
            className="mb-3"
          />

          <div className="mb-3">
            <div className="mb-1.5 text-xs font-medium text-ink-500">Tools it can use</div>
            <div className="flex flex-wrap gap-2">
              {Object.keys(tools).map((t) => (
                <Chip
                  key={t}
                  label={t}
                  title={tools[t]}
                  active={form.tools.includes(t)}
                  onClick={() => toggle("tools", t)}
                />
              ))}
            </div>
          </div>
          <div className="mb-4">
            <div className="mb-1.5 text-xs font-medium text-ink-500">Skills it has access to</div>
            <div className="flex flex-wrap gap-2">
              {Object.keys(skills).map((s) => (
                <Chip
                  key={s}
                  label={s}
                  title={skills[s]}
                  active={form.skills.includes(s)}
                  onClick={() => toggle("skills", s)}
                />
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              tone="primary"
              icon={busy ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />}
              disabled={busy || !!nameError}
              onClick={save}
            >
              Save
            </Button>
            <Button
              icon={<X className="h-4 w-4" />}
              onClick={() => {
                setForm(EMPTY_FORM);
                setEditingExisting(false);
              }}
            >
              Clear
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function Chip({ label, title, active, onClick }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors
        ${active ? "border-brand-400 bg-brand-100 text-brand-700" : "border-ink-200 bg-white text-ink-600 hover:bg-ink-50"}`}
    >
      {label}
    </button>
  );
}
