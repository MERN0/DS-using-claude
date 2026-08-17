import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ShieldCheck, PencilLine, Eye, EyeOff, Save, Trash2 } from "lucide-react";
import { Card, CardBody, SectionTitle, Badge, Button, Textarea, Spinner } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";

export default function MemoryPanel({ client, baselineMemory }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showBaseline, setShowBaseline] = useState(false);
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getMemory(client).then((data) => {
      if (!cancelled) {
        setText(data.text);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [client]);

  async function save() {
    setSaving(true);
    try {
      await api.putMemory(client, text);
      toast("Memory rule saved.", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    try {
      await api.deleteMemory(client);
      setText("");
      toast("Memory rule deleted.", "info");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardBody>
          <SectionTitle icon={<ShieldCheck className="h-4 w-4 text-brand-600" />} badge="always active">
            Baseline rules
          </SectionTitle>
          <p className="text-sm text-ink-500 mb-3">
            These rules already apply to every project's runs, before anything below is
            added. Read-only here &mdash; edit the project-specific addition instead.
          </p>
          <Button size="sm" icon={showBaseline ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />} onClick={() => setShowBaseline((v) => !v)}>
            {showBaseline ? "Hide baseline rules" : "Show baseline rules"}
          </Button>
          <AnimatePresence initial={false}>
            {showBaseline && (
              <motion.pre
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="thin-scroll mt-3 max-h-80 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-ink-100 bg-ink-50 p-3.5 font-mono text-[12.5px] leading-relaxed text-ink-700"
              >
                {baselineMemory || "(no baseline rules file found)"}
              </motion.pre>
            )}
          </AnimatePresence>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <SectionTitle icon={<PencilLine className="h-4 w-4 text-brand-600" />}>
            This project's addition
          </SectionTitle>
          <p className="text-sm text-ink-500 mb-3">
            A standing instruction, always in effect for this project's runs (e.g. "Variant
            is always N/A for this project"). Appended after the baseline rules above &mdash;
            write it as an addition, not a full restatement.
          </p>
          {loading ? (
            <div className="flex h-32 items-center justify-center text-ink-300">
              <Spinner className="h-5 w-5" />
            </div>
          ) : (
            <>
              <Textarea
                rows={7}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Write the rule text..."
                className="mb-3"
              />
              <div className="flex items-center gap-2">
                <Button tone="primary" icon={saving ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />} disabled={saving} onClick={save}>
                  Save
                </Button>
                <Button tone="danger" icon={<Trash2 className="h-4 w-4" />} onClick={remove}>
                  Delete
                </Button>
                {!loading && (
                  <Badge tone={text ? "brand" : "neutral"}>
                    {text ? "Custom addition saved" : "No addition yet — baseline only"}
                  </Badge>
                )}
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
