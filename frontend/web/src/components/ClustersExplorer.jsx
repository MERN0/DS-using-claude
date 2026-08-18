import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Boxes, ChevronDown, RefreshCw } from "lucide-react";
import { Card, CardBody, SectionTitle, Badge, Button, Spinner } from "./ui.jsx";
import { api, ApiError } from "../api.js";

// On-demand (button-triggered, not polled every tick) view over the
// current run's extracted/clustered data -- see workspace_reader.py.
// Deliberately not auto-refreshed on every status poll: this data can be
// sizable and the user drives when they want a fresh look, e.g. after
// resolution or drafting has clearly moved on in the live log.
export default function ClustersExplorer() {
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [manifest, setManifest] = useState(null);
  const [testcases, setTestcases] = useState([]);
  const [expanded, setExpanded] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [clusterList, manifestData, testcaseList] = await Promise.all([
        api.workspaceClusters(),
        api.workspaceManifest(),
        api.workspaceTestcases().catch(() => []),
      ]);
      setClusters(clusterList);
      setManifest(manifestData);
      setTestcases(testcaseList);
      setLoaded(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No extracted data yet -- generate a workbook first.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <SectionTitle icon={<Boxes className="h-4 w-4 text-brand-600" />}>Extracted data</SectionTitle>
        <p className="text-sm text-ink-500 mb-3">
          The requirement clusters this run built -- one cluster becomes one test case. Loads a snapshot of
          the current run's workspace; click again for a fresh look as the run progresses.
        </p>
        <Button
          size="sm"
          icon={loading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
          disabled={loading}
          onClick={load}
        >
          {loaded ? "Refresh" : "Load extracted data"}
        </Button>
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}

        {loaded && clusters.length === 0 && !error && (
          <p className="mt-3 text-sm text-ink-400">
            No clusters yet -- check back once merge-planning has run.
          </p>
        )}

        {clusters.length > 0 && (
          <div className="thin-scroll mt-3 flex max-h-[480px] flex-col gap-2 overflow-y-auto pr-1">
            {clusters.map((cluster) =>
              cluster._parse_error ? (
                <div
                  key={cluster._raw}
                  className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600"
                >
                  Couldn't parse a cluster line: {cluster._parse_error}
                </div>
              ) : (
                <ClusterRow
                  key={cluster.cluster_id}
                  cluster={cluster}
                  resolved={(manifest?.resolved_cluster_ids || []).includes(cluster.cluster_id)}
                  testcases={testcases.filter((t) => t._cluster_id === cluster.cluster_id)}
                  expanded={expanded === cluster.cluster_id}
                  onToggle={() => setExpanded((e) => (e === cluster.cluster_id ? null : cluster.cluster_id))}
                />
              )
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function ClusterRow({ cluster, resolved, testcases, expanded, onToggle }) {
  const [requirements, setRequirements] = useState(null);
  const [resolvedMarkdown, setResolvedMarkdown] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleToggle() {
    onToggle();
    if (expanded || requirements !== null) return; // already loaded, or collapsing
    setLoading(true);
    try {
      const [reqs, resolvedData] = await Promise.all([
        api.workspaceRequirements(cluster.cluster_id),
        resolved ? api.workspaceResolved(cluster.cluster_id).catch(() => null) : Promise.resolve(null),
      ]);
      setRequirements(reqs);
      setResolvedMarkdown(resolvedData?.markdown ?? null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink-100 bg-white overflow-hidden">
      <button
        onClick={handleToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-ink-50/60 transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-xs text-ink-400">{cluster.cluster_id}</span>
          <Badge tone="brand">{cluster.check_type}</Badge>
          <span className="text-xs text-ink-500">
            {cluster.requirement_count} requirement{cluster.requirement_count === 1 ? "" : "s"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Badge tone={resolved ? "success" : "neutral"}>{resolved ? "Resolved" : "Not resolved yet"}</Badge>
          <Badge tone={testcases.length > 0 ? "success" : "neutral"}>
            {testcases.length > 0 ? "Drafted" : "Not drafted yet"}
          </Badge>
          <ChevronDown
            className={`h-4 w-4 text-ink-400 transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
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
              {loading ? (
                <div className="flex justify-center py-4 text-ink-300">
                  <Spinner className="h-5 w-5" />
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {requirements && requirements.length > 0 && (
                    <div>
                      <div className="mb-1 text-xs font-medium text-ink-500">
                        Requirements in this cluster
                      </div>
                      <ul className="thin-scroll flex max-h-48 flex-col gap-1 overflow-y-auto pr-1">
                        {requirements.map((r, i) => (
                          <li
                            key={i}
                            className="rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs text-ink-700"
                          >
                            {JSON.stringify(r)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {resolvedMarkdown && (
                    <div>
                      <div className="mb-1 text-xs font-medium text-ink-500">Resolved signals/commands</div>
                      <pre className="thin-scroll max-h-56 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-ink-100 bg-white p-3 font-mono text-[12px] leading-relaxed text-ink-700">
                        {resolvedMarkdown}
                      </pre>
                    </div>
                  )}
                  {testcases.length > 0 && (
                    <div>
                      <div className="mb-1 text-xs font-medium text-ink-500">Drafted test case(s)</div>
                      <ul className="flex flex-col gap-1">
                        {testcases.map((t, i) => (
                          <li key={i} className="rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs">
                            <div className="font-medium text-ink-800">
                              {t["Test Case Objective"] || t["Test Case ID"] || `Test case ${i + 1}`}
                            </div>
                            <div className="mt-0.5 text-ink-500">{t["Test Case Description"]}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {!requirements?.length && !resolvedMarkdown && testcases.length === 0 && (
                    <p className="text-xs text-ink-400">Nothing to show for this cluster yet.</p>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
