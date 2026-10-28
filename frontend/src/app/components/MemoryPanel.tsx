"use client";

import { useState, useEffect, useCallback } from "react";

interface MemoryEntry {
  id: number;
  category: string;
  scope: string;
  project_root: string | null;
  content: string;
  summary: string;
  source: string;
  verification_status: "verified" | "unverified" | "proposed" | string;
  confidence: string | null;
  file_refs: string[];
  created_at: string;
  updated_at: string;
}

interface MemoryPanelProps {
  backendUrl: string;
}

export default function MemoryPanel({ backendUrl }: MemoryPanelProps) {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successNote, setSuccessNote] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Create form state
  const [isCreating, setIsCreating] = useState(false);
  const [formCategory, setFormCategory] = useState("engineering_lesson");
  const [formScope, setFormScope] = useState<"global" | "project">("global");
  const [formProjectRoot, setFormProjectRoot] = useState("");
  const [formSummary, setFormSummary] = useState("");
  const [formContent, setFormContent] = useState("");
  const [formSource, setFormSource] = useState("user");
  const [formStatus, setFormStatus] = useState<"unverified" | "verified" | "proposed">("unverified");

  const fetchMemories = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams();
    if (searchQuery.trim()) params.set("query", searchQuery.trim());
    if (categoryFilter) params.set("category", categoryFilter);
    if (statusFilter) params.set("verification_status", statusFilter);
    params.set("limit", "50");

    try {
      const res = await fetch(`${backendUrl}/api/memory/?${params.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        if (res.status === 503) {
          setError("Long-term memory database is not configured. DATABASE_URL must be set in the AI service.");
        } else {
          setError(data?.detail || data?.error?.message || `Failed to fetch memories (${res.status})`);
        }
        setMemories([]);
        return;
      }

      setMemories(data.entries || []);
    } catch (err: unknown) {
      const fetchErr = err as Error;
      setError(`Network error: ${fetchErr.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [backendUrl, searchQuery, categoryFilter, statusFilter]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessNote(null);

    if (!formSummary.trim() || !formContent.trim()) {
      setError("Summary and content are required.");
      return;
    }

    if (formScope === "project" && !formProjectRoot.trim()) {
      setError("Project Root is required when scope is set to 'project'.");
      return;
    }

    try {
      const res = await fetch(`${backendUrl}/api/memory/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: formCategory,
          scope: formScope,
          project_root: formScope === "project" ? formProjectRoot.trim() : null,
          summary: formSummary.trim(),
          content: formContent.trim(),
          source: formSource.trim() || "user",
          verification_status: formStatus,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || data?.error?.message || "Failed to create memory entry.");
        return;
      }

      setSuccessNote("Memory entry created successfully.");
      setIsCreating(false);
      setFormSummary("");
      setFormContent("");
      fetchMemories();
    } catch (err: unknown) {
      const fetchErr = err as Error;
      setError(`Failed to create memory: ${fetchErr.message}`);
    }
  };

  const handleDeleteMemory = async (id: number, projectRoot: string | null) => {
    if (!confirm(`Are you sure you want to delete memory #${id}?`)) return;

    setError(null);
    try {
      const url = projectRoot
        ? `${backendUrl}/api/memory/${id}?project_root=${encodeURIComponent(projectRoot)}`
        : `${backendUrl}/api/memory/${id}`;

      const res = await fetch(url, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json();
        setError(data?.detail || "Failed to delete memory.");
        return;
      }

      setSuccessNote(`Memory #${id} deleted.`);
      fetchMemories();
    } catch (err: unknown) {
      const fetchErr = err as Error;
      setError(`Error deleting memory: ${fetchErr.message}`);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-6 px-4">
      {/* Top Controls */}
      <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">🧠</span>
            <h2 className="text-base font-semibold text-zinc-100">Long-Term Memory Management</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800">
              Phase 10
            </span>
          </div>
          <p className="text-xs text-zinc-400 max-w-xl">
            Stores durable engineering lessons, architectural decisions, and bug fixes across sessions.
            Verified memories are automatically prioritized by the AI Companion during reasoning.
          </p>
        </div>

        <button
          onClick={() => setIsCreating(!isCreating)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2.5 rounded-xl transition-all shadow flex items-center justify-center gap-1.5"
        >
          <span>{isCreating ? "✕ Cancel" : "＋ Record New Memory"}</span>
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span>⚠</span>
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200">✕</button>
        </div>
      )}

      {successNote && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span>✓</span>
            <span>{successNote}</span>
          </div>
          <button onClick={() => setSuccessNote(null)} className="text-emerald-400 hover:text-emerald-200">✕</button>
        </div>
      )}

      {/* Create Memory Form Modal/Card */}
      {isCreating && (
        <form onSubmit={handleCreateMemory} className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
          <div className="text-xs font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
            Create Long-Term Memory Entry
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-zinc-400 mb-1">Category</label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="engineering_lesson">Engineering Lesson</option>
                <option value="architecture_decision">Architecture Decision</option>
                <option value="bug_fix">Bug Fix</option>
                <option value="user_preference">User Preference</option>
                <option value="failed_approach">Failed Approach</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-zinc-400 mb-1">Scope</label>
              <select
                value={formScope}
                onChange={(e) => setFormScope(e.target.value as "global" | "project")}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="global">Global (All Projects)</option>
                <option value="project">Project-Scoped</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-zinc-400 mb-1">Verification Status</label>
              <select
                value={formStatus}
                onChange={(e) => setFormStatus(e.target.value as any)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="unverified">Unverified (Standard)</option>
                <option value="verified">Verified (Confirmed by Tests/Lead)</option>
                <option value="proposed">Proposed (AI Suggestion)</option>
              </select>
            </div>
          </div>

          {formScope === "project" && (
            <div>
              <label className="block text-[11px] font-medium text-zinc-400 mb-1">Project Root (Absolute Path)</label>
              <input
                type="text"
                value={formProjectRoot}
                onChange={(e) => setFormProjectRoot(e.target.value)}
                placeholder="/absolute/path/to/project"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Summary (1-line description)</label>
            <input
              type="text"
              value={formSummary}
              onChange={(e) => setFormSummary(e.target.value)}
              placeholder="e.g. Always close async sessions cleanly"
              maxLength={512}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Detailed Content</label>
            <textarea
              rows={3}
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              placeholder="Explain the context, rationale, and instructions..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Provenance Source</label>
            <input
              type="text"
              value={formSource}
              onChange={(e) => setFormSource(e.target.value)}
              placeholder="e.g. user, post-mortem 2026-10-27"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsCreating(false)}
              className="px-3.5 py-1.5 rounded-lg border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs"
            >
              Save Memory
            </button>
          </div>
        </form>
      )}

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter memories by keyword..."
          className="flex-1 w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 placeholder-zinc-500"
        />

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="w-full sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none"
        >
          <option value="">All Categories</option>
          <option value="engineering_lesson">Engineering Lessons</option>
          <option value="architecture_decision">Architecture Decisions</option>
          <option value="bug_fix">Bug Fixes</option>
          <option value="user_preference">User Preferences</option>
          <option value="failed_approach">Failed Approaches</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-full sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none"
        >
          <option value="">All Verification States</option>
          <option value="verified">Verified Only</option>
          <option value="unverified">Unverified Only</option>
          <option value="proposed">Proposed Only</option>
        </select>
      </div>

      {/* Memories List */}
      {isLoading ? (
        <div className="p-8 text-center text-xs text-zinc-400 flex items-center justify-center gap-2">
          <span className="h-3 w-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          <span>Loading persistent memories...</span>
        </div>
      ) : memories.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-zinc-900/40 border border-zinc-800/80 text-zinc-400 text-xs">
          No memory entries found. Record new lessons or decisions above.
        </div>
      ) : (
        <div className="space-y-3">
          {memories.map((m) => (
            <div
              key={m.id}
              className="p-4 rounded-xl bg-zinc-900 border border-zinc-800/90 hover:border-zinc-700 transition-all space-y-2.5 shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  {/* Status Badge */}
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                      m.verification_status === "verified"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : m.verification_status === "proposed"
                        ? "bg-purple-950 text-purple-400 border border-purple-800"
                        : "bg-amber-950 text-amber-400 border border-amber-800"
                    }`}
                  >
                    {m.verification_status}
                  </span>

                  {/* Category Badge */}
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                    {m.category.replace("_", " ")}
                  </span>

                  {/* Scope Badge */}
                  <span className="text-[10px] font-mono text-zinc-400">
                    scope: <strong className="text-zinc-200">{m.scope}</strong>
                    {m.project_root && ` (${m.project_root})`}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-[11px] text-zinc-400 font-mono">
                  <span>Source: {m.source}</span>
                  <button
                    onClick={() => handleDeleteMemory(m.id, m.project_root)}
                    className="text-red-400 hover:text-red-300 font-sans text-xs hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-zinc-100">{m.summary}</h4>
                <p className="text-xs text-zinc-300 mt-1 whitespace-pre-wrap leading-relaxed">
                  {m.content}
                </p>
              </div>

              {m.file_refs && m.file_refs.length > 0 && (
                <div className="pt-2 border-t border-zinc-800/60 flex flex-wrap gap-1.5 text-[10px] font-mono text-zinc-400">
                  <span>Related files:</span>
                  {m.file_refs.map((ref) => (
                    <span key={ref} className="bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 text-zinc-300">
                      {ref}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
