import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, RotateCcw, FolderOpen } from "lucide-react";
import { api } from "./api.js";
import { ToastProvider } from "./components/Toast.jsx";
import Sidebar from "./components/Sidebar.jsx";
import MemoryPanel from "./components/MemoryPanel.jsx";
import SkillsPanel from "./components/SkillsPanel.jsx";
import SubagentsPanel from "./components/SubagentsPanel.jsx";
import GeneratePanel from "./components/GeneratePanel.jsx";
import { Spinner, Button } from "./components/ui.jsx";

const STORAGE_KEY_CLIENT = "sys5.currentClient";
const STORAGE_KEY_TAB = "sys5.tab";
const VALID_TABS = ["memory", "skills", "subagents", "generate"];

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
      <div className="flex h-screen items-center justify-center p-6">
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
      <div className="flex h-screen items-center justify-center text-brand-400">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <ToastProvider>
      {/* Viewport-locked app shell: this outer container never scrolls --
          only the <main> region below does. This is what makes the app
          read as a desktop tool with a persistent frame instead of a
          webpage where the whole document grows and the nav scrolls away
          with it. */}
      <div className="flex h-screen overflow-hidden bg-ink-50/40">
        <Sidebar
          clients={clients}
          currentClient={currentClient}
          onSelectClient={selectClient}
          onClientCreated={onCreated}
          tab={tab}
          onChangeTab={changeTab}
        />

        <main className="thin-scroll min-w-0 flex-1 overflow-y-auto">
          {!currentClient ? (
            <div className="flex h-full items-center justify-center p-8">
              <div className="max-w-sm text-center text-ink-400">
                <FolderOpen className="mx-auto mb-3 h-10 w-10 text-ink-300" />
                <p className="text-sm">Pick or create a project in the sidebar to get started.</p>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-4xl px-6 py-8">
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
                      mcpEnabled={config.mcp_enabled}
                      onMcpEnabledChange={(enabled) => setConfig((c) => ({ ...c, mcp_enabled: enabled }))}
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
            </div>
          )}
        </main>
      </div>
    </ToastProvider>
  );
}
