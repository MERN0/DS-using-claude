import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Waypoints, ArrowRight, AlertTriangle, RotateCcw } from "lucide-react";
import { api } from "./api.js";
import { ToastProvider } from "./components/Toast.jsx";
import ClientPicker from "./components/ClientPicker.jsx";
import TabNav from "./components/TabNav.jsx";
import MemoryPanel from "./components/MemoryPanel.jsx";
import SkillsPanel from "./components/SkillsPanel.jsx";
import SubagentsPanel from "./components/SubagentsPanel.jsx";
import GeneratePanel from "./components/GeneratePanel.jsx";
import { Spinner, Button } from "./components/ui.jsx";

const STORAGE_KEY_CLIENT = "sys5.currentClient";
const STORAGE_KEY_TAB = "sys5.tab";
const VALID_TABS = ["memory", "skills", "subagents", "generate"];

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-ink-100 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-pop">
            <Waypoints className="h-5 w-5" />
          </div>
          <span className="text-[15px] font-semibold text-ink-900">SYS5 Test Case Generator</span>
        </div>
        <span className="hidden items-center gap-1.5 text-sm text-ink-400 sm:flex">
          SYS2 requirements <ArrowRight className="h-3.5 w-3.5" /> SYS5 test cases
        </span>
      </div>
    </header>
  );
}

export default function App() {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [clients, setClients] = useState([]);
  const [currentClient, setCurrentClient] = useState(null);
  const [tab, setTab] = useState("memory");

  useEffect(() => {
    let cancelled = false;
    setConfigError(null);
    api
      .getConfig()
      .then((cfg) => {
        if (cancelled) return;
        setConfig(cfg);
        setClients(cfg.clients);
        // Restore the last-used project/tab, but only if that project still
        // exists -- a stale localStorage entry (project deleted since the
        // last visit) must fall back to "pick a project" rather than
        // pointing at a client that no longer resolves server-side.
        const savedClient = localStorage.getItem(STORAGE_KEY_CLIENT);
        if (savedClient && cfg.clients.includes(savedClient)) {
          setCurrentClient(savedClient);
          const savedTab = localStorage.getItem(STORAGE_KEY_TAB);
          if (savedTab && VALID_TABS.includes(savedTab)) setTab(savedTab);
        }
      })
      .catch((e) => {
        if (!cancelled) setConfigError(e.message || "Couldn't load configuration.");
      });
    return () => {
      cancelled = true;
    };
  }, [loadAttempt]);

  function selectClient(name) {
    setCurrentClient(name);
    setTab("memory");
    localStorage.setItem(STORAGE_KEY_CLIENT, name);
    localStorage.setItem(STORAGE_KEY_TAB, "memory");
  }

  function onCreated(name) {
    setClients((c) => (c.includes(name) ? c : [...c, name]));
    selectClient(name);
  }

  function changeTab(next) {
    setTab(next);
    localStorage.setItem(STORAGE_KEY_TAB, next);
  }

  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-sm text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="text-[15px] font-semibold text-ink-900">Couldn't load the dashboard</h1>
          <p className="mt-1.5 text-sm text-ink-500">{configError}</p>
          <Button
            tone="primary"
            className="mt-4"
            icon={<RotateCcw className="h-4 w-4" />}
            onClick={() => setLoadAttempt((n) => n + 1)}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex min-h-screen items-center justify-center text-brand-400">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <ToastProvider>
      <Header />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <ClientPicker
          clients={clients}
          currentClient={currentClient}
          onSelect={selectClient}
          onCreated={onCreated}
        />

        {currentClient && (
          <>
            <TabNav active={tab} onChange={changeTab} />
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                role="tabpanel"
                id={`tabpanel-${tab}`}
                aria-labelledby={`tab-${tab}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18 }}
              >
                {tab === "memory" && (
                  <MemoryPanel client={currentClient} baselineMemory={config.baseline_memory} />
                )}
                {tab === "skills" && (
                  <SkillsPanel client={currentClient} skills={config.skills} domains={config.domains} />
                )}
                {tab === "subagents" && (
                  <SubagentsPanel
                    client={currentClient}
                    builtIn={config.built_in_subagents}
                    tools={config.tools}
                    skills={config.skills}
                  />
                )}
                {tab === "generate" && (
                  <GeneratePanel
                    client={currentClient}
                    domains={config.domains}
                    outputFormats={config.output_formats}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </>
        )}
      </main>
      <footer className="py-10 text-center text-xs text-ink-300">
        Runs locally · configuration lives under{" "}
        <code className="text-ink-400">clients/&lt;project&gt;/</code>
      </footer>
    </ToastProvider>
  );
}
