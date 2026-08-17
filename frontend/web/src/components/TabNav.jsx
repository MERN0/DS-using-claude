import { motion } from "framer-motion";
import { BookMarked, GraduationCap, Users, PlayCircle } from "lucide-react";

const TABS = [
  { key: "memory", label: "Memory", icon: BookMarked },
  { key: "skills", label: "Skills", icon: GraduationCap },
  { key: "subagents", label: "Subagents", icon: Users },
  { key: "generate", label: "Generate", icon: PlayCircle },
];

export default function TabNav({ active, onChange }) {
  return (
    <div className="mb-6 flex gap-1 rounded-xl border border-ink-100 bg-white/70 p-1 backdrop-blur-sm w-fit">
      {TABS.map(({ key, label, icon: Icon }) => {
        const isActive = active === key;
        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={`relative flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors
              ${isActive ? "text-brand-700" : "text-ink-500 hover:text-ink-800"}`}
          >
            {isActive && (
              <motion.span
                layoutId="tab-pill"
                className="absolute inset-0 rounded-lg bg-brand-100"
                transition={{ type: "spring", stiffness: 500, damping: 35 }}
              />
            )}
            <Icon className="relative h-4 w-4" />
            <span className="relative">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
