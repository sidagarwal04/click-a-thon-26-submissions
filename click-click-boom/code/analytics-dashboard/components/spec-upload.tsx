'use client';

import { useState, useRef, useEffect } from 'react';
import { Upload, FileText, Loader2, CheckCircle, XCircle, ExternalLink, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface IngestionResult {
  status: string;
  proposal_id?: string;
  table_name?: string;
  ddl?: string;
  revisions?: number;
  regression_passed?: boolean;
  trace_url?: string;
  reason?: string;
  test_results?: any[];
  error?: string;
}

export function SpecUpload() {
  const [specName, setSpecName] = useState('');
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [eventsFile, setEventsFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [toolCalls, setToolCalls] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!specName || !specFile || !eventsFile) return;

    setIsUploading(true);
    setResult(null);
    setLogs([]);
    setToolCalls([]);

    // Read spec file content
    const specMarkdown = await specFile.text();

    const formData = new FormData();
    formData.append('specName', specName);
    formData.append('specMarkdown', specMarkdown);
    formData.append('eventsFile', eventsFile);

    try {
      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      // Read the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'log') {
                const emoji = data.stage === 'init' ? '🚀' :
                              data.stage === 'trace' ? '🔍' :
                              data.stage === 'error' ? '❌' :
                              data.stage === 'warning' ? '⚠️' :
                              data.stage === 'complete' ? '✅' :
                              data.stage === 'tool' ? '🔧' :
                              '📝';

                // Highlight tool calls
                let message = data.message;
                if (data.stage === 'tool' || message.includes('tool_call') ||
                    message.includes('list_context_sections') ||
                    message.includes('lookup_context') ||
                    message.includes('run_query')) {
                  message = `🔧 TOOL: ${message}`;
                }

                setLogs(prev => [...prev, `${emoji} ${message}`]);
              } else if (data.type === 'complete') {
                setResult(data.result);
                if (data.result.status === 'executed') {
                  setLogs(prev => [...prev,
                    '✅ Pipeline completed successfully!',
                    `📊 Table: ${data.result.table_name}`,
                    `🔄 Revisions: ${data.result.revisions}`,
                    `🧪 Tests: ${data.result.regression_passed ? 'PASSED' : 'FAILED'}`,
                  ]);
                } else if (data.result.status === 'needs_rework') {
                  setLogs(prev => [...prev, `⚠️ Needs rework: ${data.result.reason}`]);
                }
              } else if (data.type === 'error') {
                setLogs(prev => [...prev, `❌ ${data.message}`]);
                setResult({ status: 'failed', error: data.message });
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      setResult({ status: 'failed', error: String(error) });
      setLogs(prev => [...prev, `❌ Network error: ${error}`]);
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setEventsFile(file);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Form */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <div className="mb-6 space-y-2">
          <h2 className="text-2xl font-bold text-white">Ingest New Spec</h2>
          <p className="text-zinc-400">
            Upload a feature spec and sample events to trigger the full ingestion pipeline
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Spec Name */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              Spec Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={specName}
              onChange={(e) => setSpecName(e.target.value)}
              placeholder="e.g., express_checkout"
              disabled={isUploading}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-white placeholder-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              required
            />
          </div>

          {/* Spec Markdown File */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              Spec Markdown <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-4">
              <label className="flex flex-1 cursor-pointer items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 transition-colors hover:border-zinc-600 hover:bg-zinc-800/70">
                <FileText className="h-5 w-5 text-zinc-400" />
                <span className="flex-1 text-sm text-zinc-400">
                  {specFile ? specFile.name : 'Choose spec.md file...'}
                </span>
                <input
                  type="file"
                  accept=".md,.markdown"
                  onChange={(e) => setSpecFile(e.target.files?.[0] || null)}
                  disabled={isUploading}
                  className="hidden"
                  required
                />
              </label>
            </div>
            <p className="text-xs text-zinc-500">
              Upload your feature specification in markdown format
            </p>
          </div>

          {/* Events File Upload */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              Sample Events (NDJSON) <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-4">
              <label className="flex flex-1 cursor-pointer items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 transition-colors hover:border-zinc-600 hover:bg-zinc-800/70">
                <FileText className="h-5 w-5 text-zinc-400" />
                <span className="flex-1 text-sm text-zinc-400">
                  {eventsFile ? eventsFile.name : 'Choose NDJSON file...'}
                </span>
                <input
                  type="file"
                  accept=".ndjson,.jsonl,.json"
                  onChange={handleFileChange}
                  disabled={isUploading}
                  className="hidden"
                  required
                />
              </label>
            </div>
            <p className="text-xs text-zinc-500">
              Upload a file with one JSON event per line (NDJSON format)
            </p>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isUploading || !specName || !specFile || !eventsFile}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Processing... (this may take 2-5 minutes)
              </>
            ) : (
              <>
                <Upload className="h-5 w-5" />
                Run Ingestion Pipeline
              </>
            )}
          </button>
        </form>
      </div>

      {/* Logs */}
      {logs.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h3 className="mb-4 flex items-center justify-between text-lg font-semibold text-white">
            <span>Pipeline Logs</span>
            {isUploading && <Loader2 className="h-5 w-5 animate-spin text-blue-500" />}
          </h3>
          <div className="max-h-96 space-y-1 overflow-y-auto rounded-lg bg-zinc-950 p-4 font-mono text-sm">
            {logs.map((log, i) => (
              <div key={i} className="text-zinc-300 leading-relaxed">
                {log}
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className={cn(
          'rounded-lg border p-6',
          result.status === 'executed'
            ? 'border-green-500/20 bg-green-500/5'
            : result.status === 'needs_rework'
            ? 'border-yellow-500/20 bg-yellow-500/5'
            : 'border-red-500/20 bg-red-500/5'
        )}>
          <div className="flex items-start gap-4">
            {result.status === 'executed' ? (
              <CheckCircle className="h-6 w-6 shrink-0 text-green-500" />
            ) : result.status === 'needs_rework' ? (
              <AlertCircle className="h-6 w-6 shrink-0 text-yellow-500" />
            ) : (
              <XCircle className="h-6 w-6 shrink-0 text-red-500" />
            )}

            <div className="flex-1 space-y-4">
              <div>
                <h3 className={cn(
                  'text-lg font-semibold',
                  result.status === 'executed'
                    ? 'text-green-400'
                    : result.status === 'needs_rework'
                    ? 'text-yellow-400'
                    : 'text-red-400'
                )}>
                  {result.status === 'executed' && 'Pipeline Completed Successfully'}
                  {result.status === 'needs_rework' && 'Pipeline Needs Rework'}
                  {result.status === 'failed' && 'Pipeline Failed'}
                </h3>
              </div>

              {result.table_name && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-zinc-500">Table Name:</span>
                      <div className="mt-1 font-mono text-white">{result.table_name}</div>
                    </div>
                    <div>
                      <span className="text-zinc-500">Proposal ID:</span>
                      <div className="mt-1 font-mono text-xs text-zinc-400">{result.proposal_id}</div>
                    </div>
                    <div>
                      <span className="text-zinc-500">Revisions:</span>
                      <div className="mt-1 text-white">{result.revisions}</div>
                    </div>
                    <div>
                      <span className="text-zinc-500">Regression Tests:</span>
                      <div className={cn(
                        'mt-1 font-medium',
                        result.regression_passed ? 'text-green-400' : 'text-red-400'
                      )}>
                        {result.regression_passed ? 'PASSED' : 'FAILED'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {result.ddl && (
                <div className="space-y-2">
                  <span className="text-sm text-zinc-500">Generated DDL:</span>
                  <pre className="rounded-lg bg-zinc-950 p-4 text-xs text-zinc-300 overflow-x-auto">
                    {result.ddl}
                  </pre>
                </div>
              )}

              {result.reason && (
                <div className="rounded-lg bg-zinc-950 p-4">
                  <span className="text-sm text-zinc-500">Reason:</span>
                  <p className="mt-1 text-sm text-white">{result.reason}</p>
                </div>
              )}

              {result.error && (
                <div className="rounded-lg bg-zinc-950 p-4">
                  <span className="text-sm text-zinc-500">Error:</span>
                  <p className="mt-1 text-sm text-red-400">{result.error}</p>
                </div>
              )}

              {result.trace_url && (
                <a
                  href={result.trace_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300"
                >
                  View Langfuse Trace
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
