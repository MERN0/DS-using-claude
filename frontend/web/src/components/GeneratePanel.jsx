import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloud,
  PlayCircle,
  Download,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  Terminal,
} from "lucide-react";
import { Card, CardBody, SectionTitle, Button, Input, Select, Spinner, Badge } from "./ui.jsx";
import { api } from "../api.js";
import { useToast } from "./Toast.jsx";
import TodoChecklist from "./TodoChecklist.jsx";
import UsagePanel from "./UsagePanel.jsx";
import ClustersExplorer from "./ClustersExplorer.jsx";

const StepBadge = ({ n }) => (
  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-600 text-[12px] font-semibold text-white">
    {n}
  </span>
);

export default function GeneratePanel({ client, domains, outputFormats }) {
  const [domain, setDomain] = useState(domains[0]?.key || "");
  const [format, setFormat] = useState(outputFormats[0] || "xlsx");
  const [version, setVersion] = useState("");
  const [username, setUsername] = useState("");

  const [files, setFiles] = useState([]);
  const [uploadId, setUploadId] = useState(null);
  const [uploadedNames, setUploadedNames] = useState([]);
  const [reqFile, setReqFile] = useState("");
  const [uploading, setUploading] = useState(false);

  const [job, setJob] = useState({
    status: "idle", // idle | starting | running | done | error
    log: [],
    error: null,
    todos: [],
    currentPhase: null,
    subagentUsage: {},
    skillUsage: {},
  });
  const pollRef = useRef(null);
  const sinceRef = useRef(0);
  const logBoxRef = useRef(null);
  const toast = useToast();

  useEffect(() => () => clearInterval(pollRef.current), []);

  const ready = client && uploadId && version.trim() && username.trim() && reqFile;

  async function doUpload() {
    if (!files.length) return toast("Choose files first.", "error");
    setUploading(true);
    try {
      const data = await api.upload(files);
      setUploadId(data.upload_id);
      setUploadedNames(data.files);
      setReqFile(data.files[0] || "");
      toast(`Uploaded ${data.files.length} file(s).`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setUploading(false);
    }
  }

  async function startGenerate() {
    setJob({ status: "starting", log: [], error: null });
    sinceRef.current = 0;
    try {
      await api.generate({
        client,
        domain,
        output_format: format,
        username,
        current_version: version,
        upload_id: uploadId,
        requirement_filename: reqFile,
      });
    } catch (e) {
      setJob({ status: "error", log: [], error: e.message });
      return;
    }

    setJob((j) => ({ ...j, status: "running" }));
    pollRef.current = setInterval(async () => {
      const status = await api.generateStatus(sinceRef.current);
      sinceRef.current = status.log_total;
      setJob((j) => {
        const log = status.log.length ? [...j.log, ...status.log] : j.log;
        return {
          ...j,
          log,
          status: status.status,
          error: status.error,
          summary: status.summary,
          todos: status.todos || [],
          currentPhase: status.current_phase,
          subagentUsage: status.subagent_usage || {},
          skillUsage: status.skill_usage || {},
        };
      });
      if (status.status !== "running") {
        clearInterval(pollRef.current);
      }
    }, 1300);
  }

  useEffect(() => {
    const el = logBoxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [job.log]);

  const running = job.status === "starting" || job.status === "running";

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardBody>
          <SectionTitle icon={<StepBadge n={1} />}>Run settings</SectionTitle>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Domain">
              <Select value={domain} onChange={(e) => setDomain(e.target.value)} className="w-full">
                {domains.map((d) => (
                  <option key={d.key} value={d.key}>
                    {d.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Output format">
              <Select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full">
                {outputFormats.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Version">
              <Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v1" />
            </Field>
            <Field label="Requested by">
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your name" />
            </Field>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <SectionTitle icon={<StepBadge n={2} />}>Input files</SectionTitle>
          <p className="text-sm text-ink-500 mb-3">
            Upload the SYS2 requirements workbook plus any supporting workbooks (signal list, command list,
            application parameters, communication matrix).
          </p>
          <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-ink-200 bg-ink-50/50 px-4 py-8 text-center transition hover:border-brand-300 hover:bg-brand-50/40">
            <UploadCloud className="h-7 w-7 text-ink-400" />
            <span className="text-sm text-ink-600">
              {files.length ? `${files.length} file(s) selected` : "Click to choose .xlsx / .xlsm files"}
            </span>
            <input
              type="file"
              multiple
              accept=".xlsx,.xlsm"
              className="hidden"
              onChange={(e) => setFiles([...e.target.files])}
            />
          </label>
          <div className="mt-3 flex items-center gap-2.5">
            <Button
              tone="primary"
              size="sm"
              icon={uploading ? <Spinner className="h-3.5 w-3.5" /> : <UploadCloud className="h-3.5 w-3.5" />}
              disabled={uploading || !files.length}
              onClick={doUpload}
            >
              Upload
            </Button>
            {uploadId && <Badge tone="success">{uploadedNames.length} file(s) uploaded</Badge>}
          </div>

          <AnimatePresence>
            {uploadedNames.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3.5"
              >
                <label className="mb-1 block text-xs font-medium text-ink-500">
                  Which uploaded file is the requirements workbook?
                </label>
                <Select
                  value={reqFile}
                  onChange={(e) => setReqFile(e.target.value)}
                  className="max-w-md w-full"
                >
                  {uploadedNames.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {uploadedNames.map((n) => (
                    <li
                      key={n}
                      className="flex items-center gap-1 rounded-md bg-ink-100 px-2 py-1 text-[11px] text-ink-600"
                    >
                      <FileSpreadsheet className="h-3 w-3" /> {n}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <SectionTitle icon={<StepBadge n={3} />}>Generate</SectionTitle>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button
              tone="success"
              size="lg"
              icon={running ? <Spinner className="h-4.5 w-4.5" /> : <PlayCircle className="h-4.5 w-4.5" />}
              disabled={!ready || running}
              onClick={startGenerate}
            >
              {running ? "Generating…" : "Generate"}
            </Button>

            {job.status === "done" && (
              <motion.a
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                href={api.downloadUrl()}
                download
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-[15px] font-medium text-white shadow-pop hover:bg-emerald-700"
              >
                <Download className="h-4.5 w-4.5" /> Download output workbook
              </motion.a>
            )}

            <StatusPill status={job.status} error={job.error} />
          </div>

          {job.summary && (
            <p className="mt-2 text-xs text-ink-500">
              {Object.entries(job.summary)
                .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
                .join(" · ")}
            </p>
          )}

          <AnimatePresence>
            {job.log.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4"
              >
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-400">
                  <Terminal className="h-3.5 w-3.5" /> Live progress
                  {running && <span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                </div>
                <pre
                  ref={logBoxRef}
                  className="thin-scroll max-h-80 overflow-y-auto whitespace-pre-wrap break-words rounded-xl bg-ink-950 p-4 font-mono text-[12px] leading-relaxed text-brand-100"
                >
                  {job.log.join("\n")}
                </pre>
              </motion.div>
            )}
          </AnimatePresence>
        </CardBody>
      </Card>

      {job.status !== "idle" && (
        <>
          <UsagePanel
            currentPhase={job.currentPhase}
            subagentUsage={job.subagentUsage}
            skillUsage={job.skillUsage}
          />
          <TodoChecklist todos={job.todos} />
          <ClustersExplorer />
        </>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-ink-500">{label}</label>
      {children}
    </div>
  );
}

function StatusPill({ status, error }) {
  if (status === "idle") return null;
  if (status === "starting" || status === "running") {
    return (
      <span className="text-sm text-ink-500">
        {status === "starting" ? "Starting…" : "Running… this can take several minutes."}
      </span>
    );
  }
  if (status === "done") {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600">
        <CheckCircle2 className="h-4 w-4" /> Done
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium text-rose-600">
      <XCircle className="h-4 w-4" /> {error || "Generation failed."}
    </span>
  );
}
