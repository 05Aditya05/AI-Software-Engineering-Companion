"use client";

import { useState } from "react";

interface IndexResult {
  success: boolean;
  indexed_files: number;
  skipped_files: number;
  removed_files: number;
  failed_files: number;
  indexed_chunks: number;
  removed_chunks: number;
  errors: Record<string, string>;
  message: string;
}

interface KnowledgePanelProps {
  backendUrl: string;
}

export default function KnowledgePanel({ backendUrl }: KnowledgePanelProps) {
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTriggerIndex = async () => {
    setIsIndexing(true);
    setError(null);
    setIndexResult(null);

    try {
      const res = await fetch(`${backendUrl}/api/knowledge/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || data?.error?.message || `Indexing failed with HTTP ${res.status}`);
        return;
      }

      setIndexResult(data);
    } catch (err: unknown) {
      const fetchError = err as Error;
      setError(`Failed to reach backend: ${fetchError.message}`);
    } finally {
      setIsIndexing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-6 px-4">
      {/* Header Card */}
      <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">📚</span>
            <h2 className="text-base font-semibold text-zinc-100">Project Knowledge & RAG Indexing</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
              Phase 9
            </span>
          </div>
          <p className="text-xs text-zinc-400 max-w-xl">
            Parses project files with the syntax-aware HybridChunker, generates 768-dimensional embeddings,
            and stores differential fingerprints in PostgreSQL/pgvector for sub-second semantic retrieval.
          </p>
        </div>

        <button
          onClick={handleTriggerIndex}
          disabled={isIndexing}
          className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-xs px-4 py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 shadow"
        >
          {isIndexing ? (
            <>
              <span className="h-3 w-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Indexing Project...</span>
            </>
          ) : (
            <>
              <span>⚡ Trigger Incremental Index</span>
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
              <p className="font-semibold">Indexing Error</p>
              <p>{error}</p>
            </div>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200">✕</button>
        </div>
      )}

      {/* Indexing Summary Stats */}
      {indexResult && (
        <div className="space-y-4">
          <div className="p-5 rounded-2xl bg-zinc-900/90 border border-zinc-800 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span className="text-xs font-semibold text-zinc-200">Last Index Run Status</span>
              </div>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2.5 py-0.5 rounded border border-emerald-800">
                {indexResult.message}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Indexed Files</div>
                <div className="text-lg font-bold text-cyan-400 mt-1">{indexResult.indexed_files}</div>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Chunks Stored</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{indexResult.indexed_chunks}</div>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Skipped (Unchanged)</div>
                <div className="text-lg font-bold text-zinc-400 mt-1">{indexResult.skipped_files}</div>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Pruned Files</div>
                <div className="text-lg font-bold text-amber-400 mt-1">{indexResult.removed_files}</div>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Pruned Chunks</div>
                <div className="text-lg font-bold text-amber-400 mt-1">{indexResult.removed_chunks}</div>
              </div>
              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80">
                <div className="text-[10px] text-zinc-400 uppercase font-mono">Failures</div>
                <div className="text-lg font-bold text-red-400 mt-1">{indexResult.failed_files}</div>
              </div>
            </div>

            {Object.keys(indexResult.errors).length > 0 && (
              <div className="p-3 rounded-xl bg-red-950/20 border border-red-900/40 text-xs text-red-300">
                <p className="font-semibold mb-1">Encountered File Errors:</p>
                <ul className="list-disc list-inside space-y-0.5 font-mono text-[11px]">
                  {Object.entries(indexResult.errors).map(([path, err]) => (
                    <li key={path}>{path}: {err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Information & Usage Guide */}
      <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 text-xs text-zinc-400 space-y-3">
        <h3 className="font-semibold text-zinc-300 flex items-center gap-2">
          <span>💡</span>
          <span>How Semantic Retrieval Operates</span>
        </h3>
        <p className="leading-relaxed">
          Once indexed, the AI Companion's <code className="bg-zinc-800 text-cyan-300 px-1 py-0.5 rounded font-mono">semantic_search</code> tool
          is automatically available during conversation. When you ask questions about architecture, authentication flows, or design decisions in the <strong>Chat tab</strong>,
          the agent queries vector similarity against PostgreSQL and grounds its response with precise file paths and line ranges.
        </p>
      </div>
    </div>
  );
}
