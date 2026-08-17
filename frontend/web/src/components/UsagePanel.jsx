import { motion } from "framer-motion";
import { Activity, Bot, GraduationCap } from "lucide-react";
import { Card, CardBody, SectionTitle, Badge } from "./ui.jsx";

function formatSeconds(s) {
  if (s < 1) return "<1s";
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

// Live "what's actually happening" view -- which subagent is running right
// now, and running tallies of every subagent/skill this run has touched so
// far. Replaces raw-log-scanning as the primary way to see run progress;
// the log itself stays available, just no longer the only signal.
export default function UsagePanel({ currentPhase, subagentUsage, skillUsage }) {
  const subagents = Object.entries(subagentUsage || {});
  const skills = Object.entries(skillUsage || {});
  if (!currentPhase && subagents.length === 0 && skills.length === 0) return null;

  return (
    <Card>
      <CardBody>
        <SectionTitle icon={<Activity className="h-4 w-4 text-brand-600" />}>Activity</SectionTitle>

        {currentPhase && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-3 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm"
          >
            <span className="live-dot h-2 w-2 shrink-0 rounded-full bg-brand-500" />
            <span className="text-brand-700">
              Currently running <strong>{currentPhase.subagent}</strong>
              {currentPhase.description ? ` — ${currentPhase.description}` : ""}
            </span>
          </motion.div>
        )}

        {subagents.length > 0 && (
          <div className="mb-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-500">
              <Bot className="h-3.5 w-3.5" /> Subagents
            </div>
            <div className="flex flex-wrap gap-1.5">
              {subagents.map(([name, u]) => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1.5 rounded-full border border-ink-100 bg-white px-2.5 py-1 text-[12px] text-ink-600"
                >
                  <span className="font-medium text-ink-800">{name}</span>
                  <Badge tone={u.errors > 0 ? "danger" : "neutral"}>
                    {u.calls}× · {formatSeconds(u.total_seconds)}
                    {u.errors > 0 ? ` · ${u.errors} err` : ""}
                  </Badge>
                </span>
              ))}
            </div>
          </div>
        )}

        {skills.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-500">
              <GraduationCap className="h-3.5 w-3.5" /> Skills read
            </div>
            <div className="flex flex-wrap gap-1.5">
              {skills.map(([name, u]) => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1.5 rounded-full border border-ink-100 bg-white px-2.5 py-1 text-[12px] text-ink-600"
                >
                  <span className="font-medium text-ink-800">{name}</span>
                  <Badge tone="neutral">{u.reads}×</Badge>
                </span>
              ))}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
