"use client";

import { useState } from "react";

interface FileChange {
  path: string;
  action: "create" | "modify" | "delete" | string;
  original_content: string | null;
  proposed_content: string | null;
  diff: string;
}

interface ValidationResult {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
  passed: boolean;
}

interface Proposal {
  id: string;
  title: string;
  description: string;
  project_root: string;
  changes: FileChange[];
  status: "proposed" | "approved" | "rejected" | "applied" | "failed" | string;
  content_hash: string;
  validation_results: ValidationResult[];
  created_at: string;
  applied_at: string | null;
  error_message: string | null;
}

interface GitStatus {
  is_git: boolean;
  branch: string | null;
  clean: boolean;
  uncommitted_changes_count: number;
  modified_files: string[];
  untracked_files: string[];
  staged_files: string[];
}

interface CodingAgentPanelProps {
  backendUrl: string;
}

export default function CodingAgentPanel({ backendUrl }: CodingAgentPanelProps) {
  // Proposal generation form
  const [projectRoot, setProjectRoot] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [filePath, setFilePath] = useState("");
  const [fileAction, setFileAction] = useState<"create" | "modify" | "delete">("create");
  const [proposedContent, setProposedContent] = useState("");

  // Active Proposal & Process State
  const [activeProposal, setActiveProposal] = useState<Proposal | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);
  const [successNote, setSuccessNote] = useState<string | null>(null);

  // Git Status Inspection
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [isCheckingGit, setIsCheckingGit] = useState(false);

  const handleCheckGitStatus = async () => {
    if (!projectRoot.trim()) {
      setError("Please specify a project root path to inspect Git status.");
      return;
    }
    setIsCheckingGit(true);
    setError(null);
    try {
      const res = await fetch(`${backendUrl}/api/agent/git-status?project_root=${encodeURIComponent(projectRoot.trim())}`);
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || "Failed to inspect git status.");
        return;
      }
      setGitStatus(data);
    } catch (err: unknown) {
      setError(`Failed to inspect git status: ${(err as Error).message}`);
    } finally {
      setIsCheckingGit(false);
    }
  };

  const handleCreateProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectRoot.trim() || !title.trim() || !filePath.trim()) {
      setError("Project Root, Title, and File Path are required.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setConflictWarning(null);
    setSuccessNote(null);

    try {
      const res = await fetch(`${backendUrl}/api/agent/proposals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          project_root: projectRoot.trim(),
          changes: [
            {
              path: filePath.trim(),
              action: fileAction,
              proposed_content: fileAction === "delete" ? null : proposedContent,
            },
          ],
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || data?.error?.message || "Failed to generate proposal.");
        return;
      }

      setActiveProposal(data);
      setSuccessNote("Change proposal generated. Files on disk have NOT been modified.");
    } catch (err: unknown) {
      setError(`Failed creating proposal: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApproveProposal = async () => {
    if (!activeProposal) return;
    setIsLoading(true);
    setError(null);
    setConflictWarning(null);

    try {
      const res = await fetch(`${backendUrl}/api/agent/proposals/${activeProposal.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_hash: activeProposal.content_hash }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          setConflictWarning("Approval rejected: Proposal content hash mismatch (anti-tampering check).");
        } else {
          setError(data?.detail || "Failed to approve proposal.");
        }
        return;
      }

      setActiveProposal(data);
      setSuccessNote("Proposal approved. Ready to apply to filesystem.");
    } catch (err: unknown) {
      setError(`Approval error: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRejectProposal = async () => {
    if (!activeProposal) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${backendUrl}/api/agent/proposals/${activeProposal.id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Declined by human reviewer." }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || "Failed to reject proposal.");
        return;
      }

      setActiveProposal(data);
      setSuccessNote("Proposal rejected. Target files remain completely untouched.");
    } catch (err: unknown) {
      setError(`Rejection error: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApplyProposal = async () => {
    if (!activeProposal) return;
    setIsLoading(true);
    setError(null);
    setConflictWarning(null);

    try {
      const res = await fetch(`${backendUrl}/api/agent/proposals/${activeProposal.id}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content_hash: activeProposal.content_hash,
          run_validation: true,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          setConflictWarning(
            data?.detail || "Stale Proposal Rejected: Target file was modified concurrently on disk. Application aborted to prevent data loss."
          );
        } else {
          setError(data?.detail || "Failed to apply proposal to filesystem.");
        }
        return;
      }

      setActiveProposal(data.proposal);
      setSuccessNote("Changes applied successfully to filesystem with post-apply validation.");
    } catch (err: unknown) {
      setError(`Apply error: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-6 px-4">
      {/* Overview Banner */}
      <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">⚡</span>
            <h2 className="text-base font-semibold text-zinc-100">Controlled Coding Agent</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              Phase 11
            </span>
          </div>
          <p className="text-xs text-zinc-400 max-w-xl">
            Proposes atomic code modifications, renders unified diffs, and enforces human approval.
            Protected by tamper-evident SHA-256 fingerprints, stale-state detection, and automatic rollback.
          </p>
        </div>
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

      {conflictWarning && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-800/80 text-amber-200 text-xs space-y-1">
          <div className="font-semibold flex items-center gap-2">
            <span>🛡</span>
            <span>Safety Guard Triggered</span>
          </div>
          <p>{conflictWarning}</p>
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

      {/* Git Working Tree Status */}
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-mono text-zinc-400">Git Status:</span>
          {gitStatus ? (
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className={`px-2 py-0.5 rounded border ${gitStatus.clean ? "bg-emerald-950/80 text-emerald-400 border-emerald-800" : "bg-amber-950/80 text-amber-400 border-amber-800"}`}>
                {gitStatus.clean ? "CLEAN" : `${gitStatus.uncommitted_changes_count} UNCOMMITTED`}
              </span>
              {gitStatus.branch && (
                <span className="text-zinc-300 bg-zinc-950 px-2 py-0.5 rounded border border-zinc-800">
                  branch: {gitStatus.branch}
                </span>
              )}
            </div>
          ) : (
            <span className="text-zinc-400">Not inspected</span>
          )}
        </div>

        <button
          onClick={handleCheckGitStatus}
          disabled={isCheckingGit}
          className="text-[11px] text-cyan-400 hover:text-cyan-300 font-mono hover:underline disabled:opacity-50"
        >
          {isCheckingGit ? "Checking..." : "Inspect Git Working Tree →"}
        </button>
      </div>

      {/* Proposal Request Form */}
      <form onSubmit={handleCreateProposal} className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
        <div className="text-xs font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
          Request Safe Code Change Proposal
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Project Root (Absolute Path)</label>
            <input
              type="text"
              value={projectRoot}
              onChange={(e) => setProjectRoot(e.target.value)}
              placeholder="e.g. e:/AI-Software-Engineering-Companion"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Proposal Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Add logging helper module"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Target File (Relative Path)</label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="src/utils/logger.py"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Action</label>
            <select
              value={fileAction}
              onChange={(e) => setFileAction(e.target.value as any)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="create">Create New File</option>
              <option value="modify">Modify Existing File</option>
              <option value="delete">Delete File</option>
            </select>
          </div>
        </div>

        {fileAction !== "delete" && (
          <div>
            <label className="block text-[11px] font-medium text-zinc-400 mb-1">Proposed Code Content</label>
            <textarea
              rows={5}
              value={proposedContent}
              onChange={(e) => setProposedContent(e.target.value)}
              placeholder="Enter new file contents or modifications..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs text-zinc-200 font-mono focus:outline-none focus:border-cyan-500 leading-relaxed"
            />
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <span className="text-[11px] text-zinc-400 italic">
            Zero filesystem writes occur until you review and explicitly approve.
          </span>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 text-white font-medium text-xs transition-colors flex items-center gap-1.5"
          >
            {isLoading ? "Analyzing..." : "Generate Proposal Diff →"}
          </button>
        </div>
      </form>

      {/* Active Proposal Diff & Review Box */}
      {activeProposal && (
        <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-100">{activeProposal.title}</h3>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                    activeProposal.status === "applied"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                      : activeProposal.status === "approved"
                      ? "bg-cyan-950 text-cyan-400 border border-cyan-800"
                      : activeProposal.status === "rejected"
                      ? "bg-red-950 text-red-400 border border-red-800"
                      : "bg-amber-950 text-amber-400 border border-amber-800"
                  }`}
                >
                  {activeProposal.status}
                </span>
              </div>
              <div className="text-[11px] font-mono text-zinc-400 mt-1">
                ID: {activeProposal.id.slice(0, 12)}... • SHA-256: {activeProposal.content_hash.slice(0, 16)}...
              </div>
            </div>

            {/* Approval / Rejection / Apply Action Controls */}
            <div className="flex items-center gap-2">
              {activeProposal.status === "proposed" && (
                <>
                  <button
                    onClick={handleRejectProposal}
                    disabled={isLoading}
                    className="px-3 py-1.5 rounded-lg border border-red-800/80 hover:bg-red-950/40 text-red-400 text-xs transition-colors"
                  >
                    Reject
                  </button>
                  <button
                    onClick={handleApproveProposal}
                    disabled={isLoading}
                    className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs transition-colors"
                  >
                    Approve Proposal ✓
                  </button>
                </>
              )}

              {activeProposal.status === "approved" && (
                <button
                  onClick={handleApplyProposal}
                  disabled={isLoading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow flex items-center gap-1.5"
                >
                  {isLoading ? "Applying & Validating..." : "Apply to Filesystem & Run Validation →"}
                </button>
              )}
            </div>
          </div>

          {/* Unified Diff Viewer */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-zinc-300">Unified Diff Preview:</div>
            {activeProposal.changes.map((c, i) => (
              <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden font-mono text-xs">
                <div className="px-3 py-2 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between text-[11px] text-zinc-400">
                  <span>File: <strong className="text-zinc-200">{c.path}</strong></span>
                  <span className="uppercase text-[10px] text-zinc-400">{c.action}</span>
                </div>
                <pre className="p-3 overflow-x-auto whitespace-pre leading-relaxed text-[11px]">
                  {c.diff ? (
                    c.diff.split("\n").map((line, idx) => {
                      let color = "text-zinc-400";
                      let bg = "transparent";
                      if (line.startsWith("+") && !line.startsWith("+++")) {
                        color = "text-emerald-400";
                        bg = "bg-emerald-950/20";
                      } else if (line.startsWith("-") && !line.startsWith("---")) {
                        color = "text-red-400";
                        bg = "bg-red-950/20";
                      } else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) {
                        color = "text-cyan-400 font-semibold";
                      }
                      return (
                        <div key={idx} className={`${color} ${bg} px-1 rounded-sm`}>
                          {line}
                        </div>
                      );
                    })
                  ) : (
                    <span className="text-zinc-400 italic">No content diff generated.</span>
                  )}
                </pre>
              </div>
            ))}
          </div>

          {/* Post-Apply Validation Results */}
          {activeProposal.validation_results && activeProposal.validation_results.length > 0 && (
            <div className="pt-3 border-t border-zinc-800 space-y-2.5">
              <div className="text-xs font-semibold text-zinc-300">Subprocess Validation Results:</div>
              {activeProposal.validation_results.map((v, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 font-mono text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-300 font-semibold">$ {v.command}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${v.passed ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-red-950 text-red-400 border border-red-800"}`}>
                      {v.passed ? "PASSED (code 0)" : `FAILED (code ${v.exit_code})`}
                    </span>
                  </div>
                  <div className="text-[10px] text-zinc-400">Duration: {v.duration_ms}ms</div>
                  {v.stdout && (
                    <pre className="p-2 rounded bg-zinc-900/60 text-[10px] text-zinc-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                      {v.stdout}
                    </pre>
                  )}
                  {v.stderr && (
                    <pre className="p-2 rounded bg-red-950/20 text-[10px] text-red-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                      {v.stderr}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
