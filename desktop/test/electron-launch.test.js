/**
 * Launch verification test for Desktop Companion (Phase 13).
 *
 * Spawns the packaged Electron executable or local electron binary,
 * verifies it initializes an active process without immediate crash,
 * and terminates it cleanly.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("path");
const fs = require("node:fs");

test("Electron Launch & Lifecycle Suite", async (t) => {
  const electronBin = path.join(__dirname, "..", "node_modules", "electron", "dist", "electron.exe");

  await t.test("electron binary exists on disk", () => {
    assert.equal(fs.existsSync(electronBin), true, "electron.exe must exist in dist folder");
  });

  await t.test("spawns electron process and remains active without crash", async () => {
    const desktopDir = path.join(__dirname, "..");
    const child = spawn(electronBin, ["."], {
      cwd: desktopDir,
      stdio: "ignore",
      detached: false,
    });

    assert.ok(child.pid, "Child process must have a valid PID");

    // Wait 2.5 seconds to ensure it does not immediately crash on syntax/import/runtime error
    await new Promise((resolve) => setTimeout(resolve, 2500));

    // Confirm process is still running (exitCode is null)
    const isRunning = child.exitCode === null && !child.killed;
    assert.equal(isRunning, true, "Electron process should remain alive and not exit prematurely");

    // Cleanly terminate
    child.kill("SIGTERM");
    await new Promise((resolve) => setTimeout(resolve, 500));
    try {
      process.kill(child.pid, "SIGKILL");
    } catch {
      // already exited
    }
  });

  await t.test("packaged ai-companion.exe exists and is executable binary", (context) => {
    const packagedExe = path.join(
      __dirname,
      "..",
      "out",
      "AI Software Engineering Companion-win32-x64",
      "ai-companion.exe"
    );
    if (!fs.existsSync(packagedExe)) {
      context.skip("Packaged ai-companion.exe not built in workspace; skipping binary check");
      return;
    }
    assert.equal(fs.existsSync(packagedExe), true, "ai-companion.exe must exist in packaged folder");
    const stat = fs.statSync(packagedExe);
    assert.ok(stat.size > 100_000_000, "Packaged binary should be > 100MB");
  });
});
