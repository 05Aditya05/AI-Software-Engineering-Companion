"use client";

import { useEffect, useState } from "react";

interface TelemetryMetrics {
  status: string;
  active_since: string;
  storage_type: string;
  buffered_turns_count: number;
  buffered_traces_count: number;
  summary: {
    total_turns: number;
    successful_turns: number;
    failed_turns: number;
    success_rate_percent: number;
    total_tool_calls: number;
    avg_turn_latency_ms: number;
    avg_llm_latency_ms: number;
    avg_tool_latency_ms: number;
  };
  token_estimates: {
    estimated_prompt_tokens_recent: number;
    estimated_response_tokens_recent: number;
    is_token_count_estimated: boolean;
    note: string;
  };
  tool_usage_breakdown: Record<string, number>;
}

interface ToolTrace {
  trace_id: string;
  timestamp: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  duration_ms: number;
  success: boolean;
  error_message: string | null;
  step: number | null;
}

interface ObservabilityPanelProps {
  backendUrl: string;
  wsStatus: "connecting" | "connected" | "disconnected";
}

export default function ObservabilityPanel({ backendUrl, wsStatus }: ObservabilityPanelProps) {
  const [metrics, setMetrics] = useState<TelemetryMetrics | null>(null);
  const [traces, setTraces] = useState<ToolTrace[]>([]);
  const [backendHealth, setBackendHealth] = useState<"healthy" | "unhealthy" | "checking">("checking");
  const [aiServiceHealth, setAiServiceHealth] = useState<"healthy" | "unhealthy" | "checking">("checking");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceFilter, setTraceFilter] = useState<"all" | "success" | "failure">("all");
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);

  const fetchObservabilityData = async () => {
    setIsLoading(true);
    setError(null);

    // 1. Health checks
    try {
      const bRes = await fetch(`${backendUrl}/api/health`);
      setBackendHealth(bRes.ok ? "healthy" : "unhealthy");
    } catch {
      setBackendHealth("unhealthy");
    }

    // 2. Fetch metrics
    try {
      const mRes = await fetch(`${backendUrl}/api/observability/metrics`);
      if (mRes.ok) {
        const mData: TelemetryMetrics = await mRes.json();
        setMetrics(mData);
        setAiServiceHealth("healthy");
      } else {
        setAiServiceHealth("unhealthy");
        setError(`Failed to retrieve telemetry metrics (HTTP ${mRes.status})`);
      }
    } catch (err: unknown) {
      setAiServiceHealth("unhealthy");
      const fetchErr = err as Error;
      setError(`Failed to reach telemetry endpoint: ${fetchErr.message}`);
    }

    // 3. Fetch audit traces
    try {
      const outcomeParam = traceFilter === "all" ? "" : `&outcome=${traceFilter}`;
      const tRes = await fetch(`${backendUrl}/api/observability/traces?limit=50${outcomeParam}`);
      if (tRes.ok) {
        const tData = await tRes.json();
        setTraces(tData.traces || []);
      }
    } catch {
      // Non-fatal, traces can be empty
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchObservabilityData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [traceFilter]);

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-6 px-4">
      {/* Header Card */}
      <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">📊</span>
            <h2 className="text-base font-semibold text-zinc-100">Observability & Evaluation Dashboard</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
              Phase 16
            </span>
          </div>
          <p className="text-xs text-zinc-400 max-w-2xl">
            Real-time telemetry, execution latency tracking, tool audit traces, and estimated context metrics.
            Telemetry is buffered in a thread-safe in-memory ring buffer and resets on service restart.
          </p>
        </div>

        <button
          onClick={fetchObservabilityData}
          disabled={isLoading}
          className="bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-xs px-4 py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 shadow self-start md:self-auto"
        >
          {isLoading ? (
            <>
              <span className="h-3 w-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Refreshing...</span>
            </>
          ) : (
            <>
              <span>↻ Refresh Telemetry</span>
            </>
          )}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span className="text-red-400 font-bold">⚠</span>
            <div>
              <p className="font-semibold">Observability Notice</p>
              <p>{error}</p>
            </div>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200">✕</button>
        </div>
      )}

      {/* Service Health Indicators */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-zinc-400 font-medium">Express Backend</div>
            <div className="text-xs font-semibold mt-1 flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  backendHealth === "healthy" ? "bg-emerald-400" : "bg-red-400"
                }`}
              />
              <span className={backendHealth === "healthy" ? "text-emerald-300" : "text-red-300"}>
                {backendHealth === "healthy" ? "Online (3001)" : "Unreachable"}
              </span>
            </div>
          </div>
          <span className="text-lg">⚙️</span>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-zinc-400 font-medium">FastAPI AI Service</div>
            <div className="text-xs font-semibold mt-1 flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  aiServiceHealth === "healthy" ? "bg-emerald-400" : "bg-red-400"
                }`}
              />
              <span className={aiServiceHealth === "healthy" ? "text-emerald-300" : "text-red-300"}>
                {aiServiceHealth === "healthy" ? "Online (8000)" : "Unreachable"}
              </span>
            </div>
          </div>
          <span className="text-lg">🤖</span>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-zinc-400 font-medium">WebSocket Channel</div>
            <div className="text-xs font-semibold mt-1 flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  wsStatus === "connected"
                    ? "bg-emerald-400"
                    : wsStatus === "connecting"
                    ? "bg-amber-400"
                    : "bg-zinc-500"
                }`}
              />
              <span
                className={
                  wsStatus === "connected"
                    ? "text-emerald-300"
                    : wsStatus === "connecting"
                    ? "text-amber-300"
                    : "text-zinc-400"
                }
              >
                {wsStatus === "connected" ? "Connected" : wsStatus}
              </span>
            </div>
          </div>
          <span className="text-lg">⚡</span>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-zinc-400 font-medium">Telemetry Storage</div>
            <div className="text-xs font-semibold mt-1 text-purple-300 font-mono">
              In-Memory Ring
            </div>
          </div>
          <span className="text-lg">💾</span>
        </div>
      </div>

      {/* Aggregated Metrics Cards */}
      {metrics && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="text-[11px] text-zinc-400">Total Turns</div>
              <div className="text-xl font-bold text-zinc-100 mt-1 font-mono">
                {metrics.summary.total_turns}
              </div>
              <div className="text-[10px] text-emerald-400 mt-0.5">
                {metrics.summary.success_rate_percent}% success rate
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="text-[11px] text-zinc-400">Avg Turn Latency</div>
              <div className="text-xl font-bold text-purple-300 mt-1 font-mono">
                {metrics.summary.avg_turn_latency_ms.toFixed(1)}
                <span className="text-xs font-normal text-zinc-500 ml-1">ms</span>
              </div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                LLM: {metrics.summary.avg_llm_latency_ms.toFixed(1)} ms
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="text-[11px] text-zinc-400">Total Tool Executions</div>
              <div className="text-xl font-bold text-cyan-300 mt-1 font-mono">
                {metrics.summary.total_tool_calls}
              </div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                Avg tool time: {metrics.summary.avg_tool_latency_ms.toFixed(1)} ms
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="text-[11px] text-zinc-400">Estimated Tokens (Recent)</div>
              <div className="text-xl font-bold text-amber-300 mt-1 font-mono">
                {(
                  metrics.token_estimates.estimated_prompt_tokens_recent +
                  metrics.token_estimates.estimated_response_tokens_recent
                ).toLocaleString()}
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5 italic">
                *Approximate heuristic (~4 chars/tok)
              </div>
            </div>
          </div>

          {/* Tool usage breakdown */}
          {Object.keys(metrics.tool_usage_breakdown).length > 0 && (
            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="text-xs font-semibold text-zinc-200 mb-2.5">
                Tool Invocation Distribution (Recent Session)
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(metrics.tool_usage_breakdown).map(([name, count]) => (
                  <span
                    key={name}
                    className="px-2.5 py-1 rounded-lg text-xs font-mono bg-zinc-950 border border-zinc-800 text-cyan-300 flex items-center gap-1.5"
                  >
                    <span>🔧 {name}</span>
                    <span className="text-zinc-500 font-sans">×</span>
                    <span className="font-semibold text-white">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Tool Execution Traces Audit Table */}
      <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <span>🔍</span>
              <span>Tool Execution Audit Trail</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                {traces.length} traces
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Inspect verified arguments, execution durations, and step-level outcomes. Sensitive parameters are redacted.
            </p>
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 p-1 rounded-xl text-xs self-start">
            <button
              onClick={() => setTraceFilter("all")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                traceFilter === "all"
                  ? "bg-purple-950 text-purple-300 border border-purple-800"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setTraceFilter("success")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                traceFilter === "success"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Success
            </button>
            <button
              onClick={() => setTraceFilter("failure")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                traceFilter === "failure"
                  ? "bg-red-950 text-red-300 border border-red-800"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Failure
            </button>
          </div>
        </div>

        {traces.length === 0 ? (
          <div className="p-8 text-center border border-dashed border-zinc-800 rounded-xl">
            <p className="text-sm text-zinc-400 font-medium">No tool execution traces recorded yet</p>
            <p className="text-xs text-zinc-500 mt-1">
              Ask the companion a code search, file reading, or Git inspection question to observe live tool traces.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] text-zinc-400 border-b border-zinc-800 pb-2">
                <tr>
                  <th className="py-2 px-3">Timestamp</th>
                  <th className="py-2 px-3">Tool Name</th>
                  <th className="py-2 px-3">Latency</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 font-mono">
                {traces.map((trace) => {
                  const isExpanded = expandedTraceId === trace.trace_id;
                  return (
                    <tr key={trace.trace_id} className="hover:bg-zinc-950/40 transition-colors">
                      <td className="py-2.5 px-3 text-zinc-400 whitespace-nowrap">
                        {new Date(trace.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-2.5 px-3 text-cyan-300 font-semibold flex items-center gap-1.5">
                        <span>🔧</span>
                        <span>{trace.tool_name}</span>
                        {trace.step && (
                          <span className="text-[10px] text-zinc-500 font-normal">
                            (step {trace.step})
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-300">
                        {trace.duration_ms.toFixed(1)} ms
                      </td>
                      <td className="py-2.5 px-3">
                        {trace.success ? (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                            SUCCESS
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-red-950 text-red-400 border border-red-800">
                            FAILED
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() =>
                            setExpandedTraceId(isExpanded ? null : trace.trace_id)
                          }
                          className="text-[11px] text-purple-400 hover:text-purple-300 underline font-sans"
                        >
                          {isExpanded ? "Hide" : "Inspect"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Detailed inspect card for selected trace */}
        {expandedTraceId && (
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 text-xs space-y-2 mt-4 font-mono">
            {(() => {
              const selected = traces.find((t) => t.trace_id === expandedTraceId);
              if (!selected) return null;
              return (
                <>
                  <div className="flex items-center justify-between text-zinc-400 border-b border-zinc-800 pb-1.5 font-sans">
                    <span className="font-semibold text-zinc-200">
                      Trace Details: {selected.tool_name} ({selected.trace_id})
                    </span>
                    <button
                      onClick={() => setExpandedTraceId(null)}
                      className="text-zinc-500 hover:text-zinc-300 text-sm"
                    >
                      ✕
                    </button>
                  </div>
                  <div>
                    <span className="text-zinc-500">Sanitized Arguments:</span>
                    <pre className="p-2.5 rounded bg-zinc-900 border border-zinc-800 mt-1 text-zinc-200 overflow-x-auto text-[11px]">
                      {JSON.stringify(selected.arguments, null, 2)}
                    </pre>
                  </div>
                  {selected.error_message && (
                    <div className="text-red-400">
                      <span className="text-red-500 font-semibold">Error: </span>
                      {selected.error_message}
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
