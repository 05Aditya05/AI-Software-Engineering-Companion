/**
 * Process Manager for Desktop Companion (Phase 13).
 *
 * Checks health of background companion services (FastAPI AI service, Express backend)
 * and coordinates lifecycle management.
 */

const http = require("http");

class ProcessManager {
  constructor(options = {}) {
    this.backendUrl = options.backendUrl || "http://localhost:3001";
    this.aiServiceUrl = options.aiServiceUrl || "http://localhost:8000";
    this.frontendUrl = options.frontendUrl || "http://localhost:3000";
    this.children = [];
  }

  /**
   * Ping an HTTP endpoint to check service health.
   * @param {string} url - Target URL to ping.
   * @param {number} timeoutMs - Timeout in milliseconds.
   * @returns {Promise<boolean>}
   */
  async checkEndpoint(url, timeoutMs = 2000) {
    return new Promise((resolve) => {
      try {
        const parsed = new URL(url);
        const req = http.request(
          {
            hostname: parsed.hostname,
            port: parsed.port,
            path: parsed.pathname,
            method: "GET",
            timeout: timeoutMs,
          },
          (res) => {
            resolve(res.statusCode >= 200 && res.statusCode < 400);
          }
        );

        req.on("error", () => resolve(false));
        req.on("timeout", () => {
          req.destroy();
          resolve(false);
        });
        req.end();
      } catch {
        resolve(false);
      }
    });
  }

  /**
   * Check all service statuses concurrently.
   * @returns {Promise<{ backend: boolean, aiService: boolean, frontend: boolean }>}
   */
  async checkAllServices() {
    const [backend, aiService, frontend] = await Promise.all([
      this.checkEndpoint(`${this.backendUrl}/api/health`),
      this.checkEndpoint(`${this.aiServiceUrl}/api/health/`),
      this.checkEndpoint(this.frontendUrl),
    ]);

    return { backend, aiService, frontend };
  }

  /**
   * Register a child process for tracking and termination on exit.
   * @param {import("child_process").ChildProcess} child
   */
  registerChild(child) {
    if (child) {
      this.children.push(child);
    }
  }

  /**
   * Gracefully stop all registered child processes.
   */
  stopAll() {
    for (const child of this.children) {
      try {
        if (!child.killed) {
          child.kill("SIGTERM");
        }
      } catch (err) {
        console.error("[ProcessManager] Error terminating child:", err);
      }
    }
    this.children = [];
  }
}

module.exports = ProcessManager;
