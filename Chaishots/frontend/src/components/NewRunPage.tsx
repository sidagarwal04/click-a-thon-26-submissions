import { AlertCircle, ArrowRight, Check, FileCode2, FileText, LoaderCircle, Play, UploadCloud, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchRun, processFeature, uploadFeature } from "../api";
import type { ProcessFeatureResult } from "../types";

type SubmitStage = "idle" | "uploading" | "processing" | "waiting" | "complete" | "error";

export function NewRunPage({ onRunReady }: { onRunReady: (traceId: string) => void }) {
  const [featureFolder, setFeatureFolder] = useState("");
  const [spec, setSpec] = useState<File | null>(null);
  const [events, setEvents] = useState<File | null>(null);
  const [stage, setStage] = useState<SubmitStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessFeatureResult | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [uploadComplete, setUploadComplete] = useState(false);

  const normalizedFolder = featureFolder.trim();
  const folderValid = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(normalizedFolder);
  const busy = ["uploading", "processing", "waiting"].includes(stage);
  const canSubmit = folderValid && spec !== null && events !== null && !busy;
  const progress = useMemo(() => stage === "uploading" ? 18 : stage === "processing" ? 54 : stage === "waiting" ? 88 : stage === "complete" ? 100 : 0, [stage]);

  useEffect(() => {
    if (!busy) { setElapsed(0); return; }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || !spec || !events) return;
    setError(null); setResult(null);
    try {
      if (!uploadComplete) {
        setStage("uploading");
        await uploadFeature(normalizedFolder, spec, events);
        setUploadComplete(true);
      }
      setStage("processing");
      const pipelineResult = await processFeature(normalizedFolder);
      setResult(pipelineResult);
      if (pipelineResult.langfuse_trace_id) {
        setStage("waiting");
        for (let attempt = 0; attempt < 12; attempt += 1) {
          try {
            await fetchRun(pipelineResult.langfuse_trace_id);
            setStage("complete");
            window.setTimeout(() => onRunReady(pipelineResult.langfuse_trace_id!), 650);
            return;
          } catch {
            await new Promise((resolve) => window.setTimeout(resolve, 1000));
          }
        }
        setStage("complete");
      } else {
        setStage("complete");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start this run");
      setStage("error");
    }
  }

  function reset() {
    setFeatureFolder(""); setSpec(null); setEvents(null); setStage("idle"); setError(null); setResult(null); setUploadComplete(false);
  }

  return (
    <main className="new-run-page">
      <div className="new-run-heading">
        <span className="eyebrow">Pipeline launcher</span>
        <h1>Start a new analysis run</h1>
        <p>Upload the product specification and its event stream. Clickathon will profile, instrument, load, contextualize, and analyze the feature.</p>
      </div>

      <div className="launch-layout">
        <form className="launch-card" onSubmit={submit}>
          <div className="form-section">
            <div className="section-number">01</div>
            <div className="section-content">
              <label htmlFor="feature-folder">Feature folder</label>
              <p>A unique key used to store this feature and identify its run.</p>
              <div className={`feature-input ${featureFolder && !folderValid ? "feature-input--invalid" : ""}`}><span>incoming_features /</span><input id="feature-folder" value={featureFolder} onChange={(event) => setFeatureFolder(event.target.value)} disabled={busy || uploadComplete} placeholder="02_passport_scan" autoComplete="off" /></div>
              {featureFolder && !folderValid && <small className="field-error">Use letters, numbers, underscores, or hyphens only.</small>}
            </div>
          </div>

          <div className="form-section">
            <div className="section-number">02</div>
            <div className="section-content">
              <span className="field-label">Source files</span>
              <p>Filenames are normalized to the exact names expected by the backend.</p>
              <div className="upload-grid">
                <FilePicker title="Product spec" filename="spec.md" hint="Markdown · max 256 KB" accept=".md,text/markdown,text/plain" file={spec} onChange={setSpec} icon={<FileText size={20} />} disabled={busy || uploadComplete} />
                <FilePicker title="Event stream" filename="events.ndjson" hint="NDJSON · one event per line" accept=".ndjson,.jsonl,application/x-ndjson,application/json" file={events} onChange={setEvents} icon={<FileCode2 size={20} />} disabled={busy || uploadComplete} />
              </div>
            </div>
          </div>

          {error && <div className="launch-error"><AlertCircle size={16} /><div><strong>Run could not start</strong><span>{error}</span></div></div>}

          <div className="launch-footer">
            <div className="privacy-note"><UploadCloud size={15} /><span>Files go directly to your local FastAPI backend.</span></div>
            <button className="launch-button" type="submit" disabled={!canSubmit}>{busy ? <LoaderCircle className="spin" size={16} /> : <Play size={15} fill="currentColor" />}{busy ? "Running pipeline" : stage === "error" ? uploadComplete ? "Retry processing" : "Try again" : "Upload & run"}</button>
          </div>
        </form>

        <aside className="run-progress-card">
          <div className="progress-header"><span>Run progress</span>{busy && <time>{elapsed}s elapsed</time>}</div>
          <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
          <ProgressStep label="Upload source files" description="Store spec.md and events.ndjson" state={stepState(stage, 1)} />
          <ProgressStep label="Process feature" description="Profile, generate schema, ingest, and analyze" state={stepState(stage, 2)} />
          <ProgressStep label="Publish trace" description="Make the completed run available in Langfuse" state={stepState(stage, 3)} />

          {stage === "idle" && <div className="progress-empty"><span>Ready when you are</span><p>Select both files to begin a fully traced run.</p></div>}
          {stage === "complete" && result && <div className="launch-success"><span><Check size={18} /></span><div><strong>{result.status === "completed" ? "Analysis complete" : "Run created"}</strong><p>{result.rows_loaded.toLocaleString()} rows loaded{result.table_created ? ` into ${result.table_created}` : ""}.</p></div>{result.langfuse_trace_id && <button onClick={() => onRunReady(result.langfuse_trace_id!)}>View trace <ArrowRight size={14} /></button>}<button className="secondary-action" onClick={reset}>Start another run</button></div>}
        </aside>
      </div>
    </main>
  );
}

function FilePicker({ title, filename, hint, accept, file, onChange, icon, disabled }: { title: string; filename: string; hint: string; accept: string; file: File | null; onChange: (file: File | null) => void; icon: React.ReactNode; disabled: boolean }) {
  return <label className={`file-picker ${file ? "file-picker--selected" : ""}`}><input type="file" accept={accept} disabled={disabled} onChange={(event) => onChange(event.target.files?.[0] ?? null)} /><span className="file-picker__icon">{file ? <Check size={18} /> : icon}</span><span className="file-picker__copy"><strong>{file?.name || title}</strong><span>{file ? `${formatBytes(file.size)} · saved as ${filename}` : hint}</span></span>{file && !disabled && <button type="button" aria-label={`Remove ${title}`} onClick={(event) => { event.preventDefault(); onChange(null); }}><X size={14} /></button>} {!file && <span className="choose-label">Choose file</span>}</label>;
}

function ProgressStep({ label, description, state }: { label: string; description: string; state: "pending" | "active" | "done" }) { return <div className={`progress-step progress-step--${state}`}><span className="progress-step__marker">{state === "done" ? <Check size={13} /> : state === "active" ? <LoaderCircle className="spin" size={14} /> : null}</span><div><strong>{label}</strong><p>{description}</p></div></div>; }
function stepState(stage: SubmitStage, step: number): "pending" | "active" | "done" { const order: Record<SubmitStage, number> = { idle: 0, uploading: 1, processing: 2, waiting: 3, complete: 4, error: 0 }; const current = order[stage]; return current > step ? "done" : current === step ? "active" : "pending"; }
function formatBytes(bytes: number) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
