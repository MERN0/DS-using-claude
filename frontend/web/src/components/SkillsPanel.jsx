import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { GraduationCap, Pencil, Trash2, Save, X, ChevronDown } from "lucide-react";
import { Card, CardBody, SectionTitle, Badge, Button, Input, Textarea, Select, Spinner } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";

export default function SkillsPanel({ client, skills, domains }) {
  const [overrides, setOverrides] = useState(null); // { name: description }
  const [expanded, setExpanded] = useState(null); // skill name currently open
  const toast = useToast();

  const refresh = () =>
    api
      .listSkills(client)
      .then((items) => setOverrides(Object.fromEntries(items.map((s) => [s.name, s.description]))));

  useEffect(() => {
    setOverrides(null);
    setExpanded(null);
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  if (!overrides) {
    return (
      <Card>
        <CardBody className="flex h-40 items-center justify-center text-ink-300">
          <Spinner className="h-6 w-6" />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <SectionTitle icon={<GraduationCap className="h-4 w-4 text-brand-600" />}>
          Available skills
        </SectionTitle>
        <p className="text-sm text-ink-500 mb-4">
          Every skill a subagent can load. A project with no override for a skill runs on the baseline version
          shown below &mdash; overriding one replaces it for this project only.
        </p>
        <div className="flex flex-col gap-2.5">
          {Object.entries(skills).map(([name, baseDesc]) => (
            <SkillCard
              key={name}
              client={client}
              name={name}
              baseDesc={baseDesc}
              domains={domains}
              isCustom={Object.prototype.hasOwnProperty.call(overrides, name)}
              customDesc={overrides[name]}
              expanded={expanded === name}
              onToggle={() => setExpanded((e) => (e === name ? null : name))}
              onChanged={async () => {
                await refresh();
                toast(`Saved "${name}".`, "success");
              }}
              onDeleted={async () => {
                await refresh();
                toast(`Removed override for "${name}".`, "info");
              }}
              onError={(msg) => toast(msg, "error")}
            />
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function SkillCard({
  client,
  name,
  baseDesc,
  domains,
  isCustom,
  customDesc,
  expanded,
  onToggle,
  onChanged,
  onDeleted,
  onError,
}) {
  const isDomainKnowledge = name === "domain-knowledge";
  const [mode, setMode] = useState("baseline"); // 'baseline' | 'edit'
  const [baseDomain, setBaseDomain] = useState("");
  const [baseline, setBaseline] = useState(null);
  const [form, setForm] = useState({ description: "", body: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    setMode("baseline");
    setBaseline(null);
    if (!isDomainKnowledge) loadBaseline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  async function loadBaseline(domain) {
    const data = await api.getSkillBaseline(name, domain);
    setBaseline(data.body);
  }

  async function startEdit() {
    setBusy(true);
    try {
      const data = await api.getSkill(client, name, baseDomain || undefined);
      setForm({ description: data.description, body: data.body });
      setMode("edit");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    try {
      await api.putSkill(client, name, form.description, form.body);
      setMode("baseline");
      onChanged();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(e) {
    e.stopPropagation();
    setBusy(true);
    try {
      await api.deleteSkill(client, name);
      onDeleted();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink-100 bg-white overflow-hidden">
      <button
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-4 py-3.5 text-left hover:bg-ink-50/60 transition-colors"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-ink-900 text-sm">{name}</span>
            <Badge tone={isCustom ? "success" : "neutral"}>{isCustom ? "Custom override" : "Baseline"}</Badge>
          </div>
          <p className="mt-0.5 text-xs text-ink-500 line-clamp-1">{isCustom ? customDesc : baseDesc}</p>
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-ink-400 transition-transform mt-1 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-ink-100 bg-ink-50/40"
          >
            <div className="p-4">
              {mode === "baseline" ? (
                <>
                  {isDomainKnowledge && (
                    <div className="mb-3 flex items-center gap-2">
                      <Select
                        value={baseDomain}
                        onChange={(e) => {
                          setBaseDomain(e.target.value);
                          if (e.target.value) loadBaseline(e.target.value);
                        }}
                        className="text-xs"
                      >
                        <option value="">Baseline for domain&hellip;</option>
                        {domains.map((d) => (
                          <option key={d.key} value={d.key}>
                            {d.label}
                          </option>
                        ))}
                      </Select>
                      <span className="text-xs text-ink-400">
                        domain-knowledge replaces, not adds to, the domain's own skill
                      </span>
                    </div>
                  )}
                  {baseline !== null && (
                    <pre className="thin-scroll mb-3 max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-ink-100 bg-white p-3 font-mono text-[12px] leading-relaxed text-ink-700">
                      {baseline || "(nothing to show yet)"}
                    </pre>
                  )}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      tone="primary"
                      icon={busy ? <Spinner className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
                      disabled={busy}
                      onClick={startEdit}
                    >
                      {isCustom ? "Edit override" : "Create override"}
                    </Button>
                    {isCustom && (
                      <Button
                        size="sm"
                        tone="danger"
                        icon={<Trash2 className="h-3.5 w-3.5" />}
                        disabled={busy}
                        onClick={remove}
                      >
                        Remove override
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <label className="mb-1 block text-xs font-medium text-ink-500">Description</label>
                  <Input
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="One sentence: what this covers and when to read it."
                    className="mb-2.5"
                  />
                  <label className="mb-1 block text-xs font-medium text-ink-500">Body (Markdown)</label>
                  <Textarea
                    rows={10}
                    value={form.body}
                    onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                    className="mb-3"
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      tone="primary"
                      icon={busy ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
                      disabled={busy}
                      onClick={save}
                    >
                      Save override
                    </Button>
                    <Button
                      size="sm"
                      icon={<X className="h-3.5 w-3.5" />}
                      onClick={() => setMode("baseline")}
                    >
                      Cancel
                    </Button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
