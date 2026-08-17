import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Waypoints, ArrowRight } from "lucide-react";
import { api } from "./api.js";
import { ToastProvider } from "./components/Toast.jsx";
import ClientPicker from "./components/ClientPicker.jsx";
import TabNav from "./components/TabNav.jsx";
import MemoryPanel from "./components/MemoryPanel.jsx";
import SkillsPanel from "./components/SkillsPanel.jsx";
import SubagentsPanel from "./components/SubagentsPanel.jsx";
import GeneratePanel from "./components/GeneratePanel.jsx";
import { Spinner } from "./components/ui.jsx";

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
  const [clients, setClients] = useState([]);
  const [currentClient, setCurrentClient] = useState(null);
  const [tab, setTab] = useState("memory");

  useEffect(() => {
    api.getConfig().then((cfg) => {
      setConfig(cfg);
      setClients(cfg.clients);
    });
  }, []);

  function selectClient(name) {
    setCurrentClient(name);
    setTab("memory");
  }

  function onCreated(name) {
    setClients((c) => (c.includes(name) ? c : [...c, name]));
    selectClient(name);
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
            <TabNav active={tab} onChange={setTab} />
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
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
