import { useState } from "react";
import { FolderOpen, Plus, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import { Card, CardBody, Button, Input, Select } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";

// Mirrors settings.validate_kebab_name's rule server-side -- this is a UX
// aid only, never the sole guard (the backend re-validates and is the
// actual authority; see builders.py's validate_new_client_name).
const KEBAB_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function nameHint(name) {
  if (!name) return null;
  if (name.length < 2 || name.length > 64) return "2-64 characters.";
  if (!KEBAB_RE.test(name)) return "Lowercase letters, digits, and single hyphens only, e.g. \"acme-corp\".";
  return null;
}

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
    <Card className="mb-6">
      <CardBody>
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
            <FolderOpen className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold text-ink-900">Project</h2>
            <p className="mt-0.5 text-sm text-ink-500 max-w-2xl">
              A project (client) is a folder of extra rules, skill overrides, and custom subagents layered on
              top of the standard behavior. Nothing customized yet? It still runs fine on the defaults.
            </p>

            <div className="mt-4 flex flex-wrap items-start gap-2.5">
              <Select
                value={currentClient || ""}
                onChange={(e) => e.target.value && onSelect(e.target.value)}
                className="min-w-[220px]"
              >
                <option value="">Select a project&hellip;</option>
                {clients.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
              <span className="mt-2 text-xs font-medium uppercase tracking-wide text-ink-300">or</span>
              <div className="max-w-[220px]">
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && createClient()}
                  placeholder="new-project-name"
                  className={hint ? "border-rose-300 focus:border-rose-400 focus:ring-rose-100" : ""}
                />
                {hint ? (
                  <p className="mt-1 text-xs text-rose-600">{hint}</p>
                ) : (
                  <p className="mt-1 text-xs text-ink-300">lowercase-with-hyphens</p>
                )}
              </div>
              <Button
                tone="primary"
                icon={<Plus className="h-4 w-4" />}
                disabled={busy || !newName.trim() || !!hint}
                onClick={createClient}
              >
                Use this project
              </Button>
            </div>

            {currentClient && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600"
              >
                Working on <span className="rounded-md bg-brand-50 px-1.5 py-0.5">{currentClient}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </motion.div>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
