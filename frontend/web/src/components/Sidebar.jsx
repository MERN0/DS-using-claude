import { motion } from "framer-motion";
import { Waypoints, BookMarked, GraduationCap, Users, PlayCircle } from "lucide-react";
import ClientPicker from "./ClientPicker.jsx";

const TABS = [
  { key: "memory", label: "Memory", icon: BookMarked },
  { key: "skills", label: "Skills", icon: GraduationCap },
  { key: "subagents", label: "Subagents", icon: Users },
  { key: "generate", label: "Generate", icon: PlayCircle },
];

// Persistent left app-shell rail: brand, project switcher, and section nav
// -- replaces the old top TabNav bar. Switching sections no longer reflows
// the whole page; only the main content area to the right of this scrolls
// (see App.jsx), which is what keeps this always in view like a real
// desktop tool instead of a webpage nav bar that scrolls away.
export default function Sidebar({
  clients,
  currentClient,
  onSelectClient,
  onClientCreated,
  tab,
  onChangeTab,
}) {
  function onKeyDown(e) {
    const idx = TABS.findIndex((t) => t.key === tab);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      onChangeTab(TABS[(idx + 1) % TABS.length].key);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      onChangeTab(TABS[(idx - 1 + TABS.length) % TABS.length].key);
    }
  }

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-ink-100 bg-white/80 backdrop-blur-sm">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-pop">
          <Waypoints className="h-4.5 w-4.5" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold text-ink-900">SYS5 Generator</div>
          <div className="truncate text-[11px] text-ink-400">SYS2 → SYS5 test cases</div>
        </div>
      </div>

      <ClientPicker
        clients={clients}
        currentClient={currentClient}
        onSelect={onSelectClient}
        onCreated={onClientCreated}
      />

      {currentClient && (
        <nav
          role="tablist"
          aria-label="Project sections"
          aria-orientation="vertical"
          onKeyDown={onKeyDown}
          className="flex flex-col gap-0.5 px-2.5 py-3"
        >
          {TABS.map(({ key, label, icon: Icon }) => {
            const isActive = tab === key;
            return (
              <button
                key={key}
                role="tab"
                id={`tab-${key}`}
                aria-selected={isActive}
                aria-controls={`tabpanel-${key}`}
                tabIndex={isActive ? 0 : -1}
                onClick={() => onChangeTab(key)}
                className={`relative flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors
                  ${isActive ? "text-brand-700" : "text-ink-500 hover:bg-ink-50 hover:text-ink-800"}`}
              >
                {isActive && (
                  <motion.span
                    layoutId="sidebar-tab-pill"
                    className="absolute inset-0 rounded-lg bg-brand-100"
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
                <Icon className="relative h-4 w-4 shrink-0" />
                <span className="relative">{label}</span>
              </button>
            );
          })}
        </nav>
      )}

      <div className="mt-auto px-4 py-3 text-[11px] leading-relaxed text-ink-300">
        Runs locally · configuration lives under{" "}
        <code className="text-ink-400">clients/&lt;project&gt;/</code>
      </div>
    </aside>
  );
}
