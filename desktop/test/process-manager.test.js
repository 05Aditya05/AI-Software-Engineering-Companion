/**
 * Unit tests for Desktop ProcessManager (Phase 13).
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const ProcessManager = require("../process-manager");

test("ProcessManager Suite", async (t) => {
  let mockServer;
  let serverPort;

  t.beforeEach(async () => {
    mockServer = http.createServer((req, res) => {
      if (req.url === "/api/health" || req.url === "/api/health/") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok" }));
      } else {
        res.writeHead(404);
        res.end();
      }
    });

    await new Promise((resolve) => {
      mockServer.listen(0, "127.0.0.1", () => {
        serverPort = mockServer.address().port;
        resolve();
      });
    });
  });

  t.afterEach(async () => {
    await new Promise((resolve) => mockServer.close(resolve));
  });

  await t.test("checkEndpoint returns true for reachable 200 endpoint", async () => {
    const pm = new ProcessManager();
    const result = await pm.checkEndpoint(`http://127.0.0.1:${serverPort}/api/health`);
    assert.equal(result, true);
  });

  await t.test("checkEndpoint returns false for unreachable port", async () => {
    const pm = new ProcessManager();
    // Port 1 is rarely open
    const result = await pm.checkEndpoint("http://127.0.0.1:1/nonexistent", 500);
    assert.equal(result, false);
  });

  await t.test("checkAllServices aggregates endpoints correctly", async () => {
    const pm = new ProcessManager({
      backendUrl: `http://127.0.0.1:${serverPort}`,
      aiServiceUrl: `http://127.0.0.1:${serverPort}`,
      frontendUrl: `http://127.0.0.1:1/offline`,
    });

    const status = await pm.checkAllServices();
    assert.equal(status.backend, true);
    assert.equal(status.aiService, true);
    assert.equal(status.frontend, false);
  });

  await t.test("registerChild and stopAll handles process termination", async () => {
    const pm = new ProcessManager();
    let killCalled = false;
    const mockChild = {
      killed: false,
      kill: (sig) => {
        killCalled = true;
      },
    };

    pm.registerChild(mockChild);
    assert.equal(pm.children.length, 1);

    pm.stopAll();
    assert.equal(killCalled, true);
    assert.equal(pm.children.length, 0);
  });
});
