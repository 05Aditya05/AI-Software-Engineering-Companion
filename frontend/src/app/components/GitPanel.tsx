"use client";

import { useState, useEffect, useCallback } from "react";

interface GitLogEntry {
  hash: string;
  short_hash: string;
  author: string;
  date: string;
  message: string;
}

interface GitBranchInfo {
  name: string;
  is_current: boolean;
  is_remote: boolean;
}

interface GitBlameEntry {
  commit: string;
  author: string;
  date: string;
  line_number: number;
  content: string;
}

interface GitPanelProps {
  backendUrl: string;
}

export default function GitPanel({ backendUrl }: GitPanelProps) {
  const [projectRoot, setProjectRoot] = useState<string>(".");
  const [activeSubTab, setActiveSubTab] = useState<"history" | "diff" | "commit" | "blame">("history");

  // Log state
  const [commits, setCommits] = useState<GitLogEntry[]>([]);
  const [loadingLog, setLoadingLog] = useState(false);

  // Branches state
  const [branches, setBranches] = useState<GitBranchInfo[]>([]);
  const [currentBranch, setCurrentBranch] = useState<string>("");
  const [newBranchName, setNewBranchName] = useState("");
  const [creatingBranch, setCreatingBranch] = useState(false);

  // Diff state
  const [diffType, setDiffType] = useState<"working" | "staged">("working");
  const [diffText, setDiffText] = useState("");
  const [loadingDiff, setLoadingDiff] = useState(false);

  // Commit / Stage state
  const [stagePathInput, setStagePathInput] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [stagedFiles, setStagedFiles] = useState<string[]>([]);
  const [approvalToken, setApprovalToken] = useState<string>("");
  const [stagingLoading, setStagingLoading] = useState(false);
  const [committingLoading, setCommittingLoading] = useState(false);

  // Blame state
  const [blamePath, setBlamePath] = useState("");
  const [blameEntries, setBlameEntries] = useState<GitBlameEntry[]>([]);
  const [loadingBlame, setLoadingBlame] = useState(false);

  // Status & notifications
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  const fetchBranches = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/api/git/branches?project_root=${encodeURIComponent(projectRoot)}`);
      if (res.ok) {
        const data = await res.json();
        setBranches(data.branches || []);
        setCurrentBranch(data.current_branch || "");
      }
    } catch {
      // Non-critical background fetch
    }
  }, [backendUrl, projectRoot]);

  const fetchLog = useCallback(async () => {
    setLoadingLog(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${backendUrl}/api/git/log?project_root=${encodeURIComponent(projectRoot)}&max_count=20`);
      if (res.ok) {
        const data = await res.json();
        setCommits(data.entries || []);
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Failed to load git log.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    } finally {
      setLoadingLog(false);
    }
  }, [backendUrl, projectRoot]);

  const fetchDiff = useCallback(async () => {
    setLoadingDiff(true);
    try {
      const res = await fetch(`${backendUrl}/api/git/diff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_root: projectRoot, diff_type: diffType }),
      });
      if (res.ok) {
        const data = await res.json();
        setDiffText(data.diff_text || "(No differences detected)");
      } else {
        const err = await res.json();
        setDiffText(`Error loading diff: ${err.detail || "Unknown error"}`);
      }
    } catch (err: unknown) {
      setDiffText(`Network error: ${(err as Error).message}`);
    } finally {
      setLoadingDiff(false);
    }
  }, [backendUrl, projectRoot, diffType]);

  const fetchBlame = async () => {
    if (!blamePath.trim()) return;
    setLoadingBlame(true);
    try {
      const res = await fetch(`${backendUrl}/api/git/blame`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_root: projectRoot, path: blamePath.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setBlameEntries(data.entries || []);
        setStatusMessage({ text: `Blame loaded for ${data.path} (${data.total_lines} lines)`, type: "info" });
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Failed to load blame.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    } finally {
      setLoadingBlame(false);
    }
  };

  const handleStageFiles = async () => {
    if (!stagePathInput.trim()) return;
    const paths = stagePathInput.split(",").map((p) => p.trim()).filter(Boolean);
    setStagingLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/git/stage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_root: projectRoot, paths }),
      });
      if (res.ok) {
        const data = await res.json();
        setStagedFiles(data.staged_files || []);
        setStatusMessage({ text: `Staged: ${data.staged_files?.join(", ") || "none"}`, type: "success" });
        setStagePathInput("");
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Staging failed.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    } finally {
      setStagingLoading(false);
    }
  };

  const handlePrepareCommit = async () => {
    if (!commitMessage.trim()) {
      setStatusMessage({ text: "Commit message is required.", type: "error" });
      return;
    }
    try {
      const res = await fetch(
        `${backendUrl}/api/git/stage-token?project_root=${encodeURIComponent(projectRoot)}&message=${encodeURIComponent(
          commitMessage.trim()
        )}`
      );
      if (res.ok) {
        const data = await res.json();
        setStagedFiles(data.staged_files || []);
        setApprovalToken(data.approval_token || "");
        setStatusMessage({
          text: `Approval token generated for ${data.staged_files?.length || 0} staged files. Review and confirm commit.`,
          type: "info",
        });
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Failed to generate token.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    }
  };

  const handleExecuteCommit = async () => {
    if (!approvalToken) {
      setStatusMessage({ text: "Approval token required before committing.", type: "error" });
      return;
    }
    setCommittingLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/git/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_root: projectRoot,
          message: commitMessage.trim(),
          approval_token: approvalToken,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage({
          text: `Committed successfully! Commit: ${data.commit_hash.slice(0, 7)} on branch ${data.branch || "HEAD"}`,
          type: "success",
        });
        setCommitMessage("");
        setApprovalToken("");
        setStagedFiles([]);
        fetchLog();
        fetchBranches();
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Commit rejected.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    } finally {
      setCommittingLoading(false);
    }
  };

  const handleCreateBranch = async () => {
    if (!newBranchName.trim()) return;
    setCreatingBranch(true);
    try {
      const res = await fetch(`${backendUrl}/api/git/branch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_root: projectRoot,
          branch_name: newBranchName.trim(),
          switch: true,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage({
          text: `Branch '${data.branch_name}' created and checked out!`,
          type: "success",
        });
        setNewBranchName("");
        fetchBranches();
      } else {
        const err = await res.json();
        setStatusMessage({ text: err.detail || "Failed to create branch.", type: "error" });
      }
    } catch (err: unknown) {
      setStatusMessage({ text: (err as Error).message, type: "error" });
    } finally {
      setCreatingBranch(false);
    }
  };

  useEffect(() => {
    fetchBranches();
    fetchLog();
  }, [fetchBranches, fetchLog]);

  useEffect(() => {
    if (activeSubTab === "diff") {
      fetchDiff();
    }
  }, [activeSubTab, fetchDiff]);

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-zinc-800">
        <div>
          <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <span>🌿</span>
            <span>Git Workspace Integration</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">
              Phase 12
            </span>
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Safe, human-approved git operations: log, diff, branch, stage, and commit with approval verification.
          </p>
        </div>

        {/* Current Branch and Project Root */}
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800">
            <span className="text-zinc-500 font-mono">Branch:</span>
            <span className="font-semibold text-emerald-400 font-mono">{currentBranch || "HEAD"}</span>
          </div>
          <input
            type="text"
            value={projectRoot}
            onChange={(e) => setProjectRoot(e.target.value)}
            title="Project Root Path"
            className="bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 font-mono w-44"
          />
        </div>
      </div>

      {/* Notifications */}
      {statusMessage && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
            statusMessage.type === "success"
              ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
              : statusMessage.type === "error"
              ? "bg-red-950/40 border-red-800/60 text-red-300"
              : "bg-cyan-950/40 border-cyan-800/60 text-cyan-300"
          }`}
        >
          <span>{statusMessage.text}</span>
          <button onClick={() => setStatusMessage(null)} className="text-zinc-400 hover:text-zinc-200">
            ✕
          </button>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-zinc-800 space-x-2 text-xs">
        <button
          onClick={() => setActiveSubTab("history")}
          className={`pb-2 px-3 font-medium transition-colors ${
            activeSubTab === "history"
              ? "border-b-2 border-emerald-500 text-emerald-400"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          📜 Commit History
        </button>
        <button
          onClick={() => setActiveSubTab("diff")}
          className={`pb-2 px-3 font-medium transition-colors ${
            activeSubTab === "diff"
              ? "border-b-2 border-emerald-500 text-emerald-400"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          🔍 Inspect Diff
        </button>
        <button
          onClick={() => setActiveSubTab("commit")}
          className={`pb-2 px-3 font-medium transition-colors ${
            activeSubTab === "commit"
              ? "border-b-2 border-emerald-500 text-emerald-400"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          ✍️ Stage & Commit
        </button>
        <button
          onClick={() => setActiveSubTab("blame")}
          className={`pb-2 px-3 font-medium transition-colors ${
            activeSubTab === "blame"
              ? "border-b-2 border-emerald-500 text-emerald-400"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          🔎 Line Blame
        </button>
      </div>

      {/* SUB-TAB: Commit History */}
      {activeSubTab === "history" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-200">Recent Commits ({commits.length})</h3>
            <button
              onClick={fetchLog}
              disabled={loadingLog}
              className="px-3 py-1 text-xs rounded-lg bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 transition-colors"
            >
              {loadingLog ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          <div className="space-y-2">
            {commits.map((c) => (
              <div
                key={c.hash}
                className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition-all text-xs"
              >
                <div className="flex items-center justify-between text-zinc-400 mb-1 font-mono text-[11px]">
                  <span className="text-emerald-400 font-semibold">{c.short_hash}</span>
                  <span>{c.author} • {c.date}</span>
                </div>
                <div className="text-zinc-200 font-medium">{c.message}</div>
              </div>
            ))}
            {commits.length === 0 && !loadingLog && (
              <div className="text-center py-8 text-zinc-500 text-xs">No commits found.</div>
            )}
          </div>
        </div>
      )}

      {/* SUB-TAB: Inspect Diff */}
      {activeSubTab === "diff" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setDiffType("working")}
                className={`px-3 py-1 text-xs rounded-lg font-medium ${
                  diffType === "working"
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                    : "bg-zinc-900 text-zinc-400 border border-zinc-800"
                }`}
              >
                Working Tree (Unstaged)
              </button>
              <button
                onClick={() => setDiffType("staged")}
                className={`px-3 py-1 text-xs rounded-lg font-medium ${
                  diffType === "staged"
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                    : "bg-zinc-900 text-zinc-400 border border-zinc-800"
                }`}
              >
                Staged (Cached)
              </button>
            </div>
            <button
              onClick={fetchDiff}
              disabled={loadingDiff}
              className="px-3 py-1 text-xs rounded-lg bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300"
            >
              {loadingDiff ? "Loading..." : "Refresh Diff"}
            </button>
          </div>

          <pre className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 font-mono text-[11px] text-zinc-300 overflow-x-auto whitespace-pre-wrap max-h-96">
            {diffText}
          </pre>
        </div>
      )}

      {/* SUB-TAB: Stage & Commit */}
      {activeSubTab === "commit" && (
        <div className="space-y-6">
          {/* Staging Form */}
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-200">1. Stage Files for Commit</h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={stagePathInput}
                onChange={(e) => setStagePathInput(e.target.value)}
                placeholder="Relative paths separated by comma (e.g. src/app.ts, package.json)"
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-500"
              />
              <button
                onClick={handleStageFiles}
                disabled={stagingLoading || !stagePathInput.trim()}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {stagingLoading ? "Staging..." : "Stage"}
              </button>
            </div>
            {stagedFiles.length > 0 && (
              <div className="text-[11px] text-zinc-400 font-mono">
                Currently staged: <span className="text-emerald-400">{stagedFiles.join(", ")}</span>
              </div>
            )}
          </div>

          {/* Commit Form */}
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-200">2. Commit with Approval Verification</h4>
            <textarea
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Commit message (e.g. feat: add git integration UI)"
              rows={3}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-200 placeholder-zinc-500 font-mono"
            />

            <div className="flex items-center gap-3">
              <button
                onClick={handlePrepareCommit}
                disabled={!commitMessage.trim()}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                Generate Approval Token
              </button>

              {approvalToken && (
                <button
                  onClick={handleExecuteCommit}
                  disabled={committingLoading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5"
                >
                  {committingLoading ? "Committing..." : "✓ Confirm & Execute Commit"}
                </button>
              )}
            </div>

            {approvalToken && (
              <div className="p-3 rounded-lg bg-zinc-950 border border-emerald-900/50 text-[11px] font-mono text-emerald-300">
                Token verified: <span className="text-zinc-400">{approvalToken.slice(0, 32)}...</span>
              </div>
            )}
          </div>

          {/* Branch Creation */}
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-200">3. Create & Switch Branch</h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={newBranchName}
                onChange={(e) => setNewBranchName(e.target.value)}
                placeholder="New branch name (e.g. feature/windows-companion)"
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-500 font-mono"
              />
              <button
                onClick={handleCreateBranch}
                disabled={creatingBranch || !newBranchName.trim()}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {creatingBranch ? "Creating..." : "Create & Switch"}
              </button>
            </div>
            <div className="text-[11px] text-zinc-400">
              Branches: {branches.map((b) => b.name).join(", ")}
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB: Line Blame */}
      {activeSubTab === "blame" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={blamePath}
              onChange={(e) => setBlamePath(e.target.value)}
              placeholder="Relative file path (e.g. package.json or src/app.ts)"
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-500 font-mono"
            />
            <button
              onClick={fetchBlame}
              disabled={loadingBlame || !blamePath.trim()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {loadingBlame ? "Loading..." : "Blame"}
            </button>
          </div>

          {blameEntries.length > 0 && (
            <div className="border border-zinc-800 rounded-xl overflow-x-auto max-h-96">
              <table className="w-full text-left text-[11px] font-mono">
                <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400">
                  <tr>
                    <th className="p-2 w-12 text-center">Line</th>
                    <th className="p-2 w-24">Commit</th>
                    <th className="p-2 w-28">Author</th>
                    <th className="p-2 w-24">Date</th>
                    <th className="p-2">Content</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 bg-zinc-950 text-zinc-300">
                  {blameEntries.map((b) => (
                    <tr key={b.line_number} className="hover:bg-zinc-900/40">
                      <td className="p-2 text-center text-zinc-500">{b.line_number}</td>
                      <td className="p-2 text-emerald-400">{b.commit.slice(0, 7)}</td>
                      <td className="p-2 text-zinc-400">{b.author}</td>
                      <td className="p-2 text-zinc-500">{b.date}</td>
                      <td className="p-2 whitespace-pre text-zinc-200">{b.content}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
