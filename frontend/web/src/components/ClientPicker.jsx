import { useState } from "react";
import { FolderOpen, Plus, Check } from "lucide-react";
import { Button, Input, Select } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";

// Mirrors settings.validate_kebab_name's rule server-side -- this is a UX
// aid only, never the sole guard (the backend re-validates and is the
// actual authority; see builders.py's validate_new_client_name).
const KEBAB_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function nameHint(name) {
  if (!name) return null;
  if (name.length < 2 || name.length > 64) return "2-64 characters.";
  if (!KEBAB_RE.test(name)) return 'Lowercase letters, digits, and single hyphens only, e.g. "acme-corp".';
  return null;
}

// Compact, vertical project switcher -- lives in the Sidebar app-shell
// rather than as its own full-width page section, so picking/creating a
// project reads as app chrome (like a workspace switcher), not a primary
// piece of page content competing with the actual work below it.
export default function ClientPicker({ clients, currentClient, onSelect, onCreated }) {
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const hint = nameHint(newName.trim());

  async function createClient() {
    const name = newName.trim();
    if (!name || hint) return;
    setBusy(true);
    try {
      await api.createClient(name);
      onCreated(name);
      setNewName("");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-ink-100 px-4 py-4">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-400">
        <FolderOpen className="h-3.5 w-3.5" /> Project
      </div>

      {currentClient && (
        <div className="mb-2.5 flex items-center gap-1.5 rounded-lg bg-brand-50 px-2.5 py-1.5 text-sm font-medium text-brand-700">
          <Check className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{currentClient}</span>
        </div>
      )}

      <label htmlFor="client-select" className="sr-only">
        Select an existing project
      </label>
      <Select
        id="client-select"
        value={currentClient || ""}
        onChange={(e) => e.target.value && onSelect(e.target.value)}
        className="w-full"
      >
        <option value="">{clients.length ? "Switch project…" : "No projects yet"}</option>
        {clients.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </Select>

      <div className="mt-2.5 flex items-center gap-2">
        <div className="h-px flex-1 bg-ink-100" />
        <span className="text-[10px] font-medium uppercase tracking-wide text-ink-300">new project</span>
        <div className="h-px flex-1 bg-ink-100" />
      </div>

      <div className="mt-2.5">
        <label htmlFor="client-new-name" className="sr-only">
          New project name
        </label>
        <Input
          id="client-new-name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && createClient()}
          placeholder="new-project-name"
          className={`text-sm ${hint ? "border-rose-300 focus:border-rose-400 focus:ring-rose-100" : ""}`}
        />
        {hint ? (
          <p className="mt-1 text-[11px] text-rose-600">{hint}</p>
        ) : (
          <p className="mt-1 text-[11px] text-ink-300">lowercase-with-hyphens</p>
        )}
        <Button
          tone="primary"
          size="sm"
          className="mt-2 w-full"
          icon={<Plus className="h-3.5 w-3.5" />}
          disabled={busy || !newName.trim() || !!hint}
          onClick={createClient}
        >
          Create &amp; use
        </Button>
      </div>
    </div>
  );
}
