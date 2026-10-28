/**
 * Integration and routing tests for the Express gateway proxy routes.
 *
 * Uses Node's built-in test runner (node:test, node:assert) and mocks upstream fetch.
 */

import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import app from "../src/app";

// Helper to make local HTTP requests to the Express app
function makeRequest(
  server: http.Server,
  options: {
    method: string;
    path: string;
    headers?: Record<string, string>;
    body?: any;
  }
): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const address = server.address();
    if (!address || typeof address === "string") {
      return reject(new Error("Server address not available"));
    }

    const req = http.request(
      {
        host: "127.0.0.1",
        port: address.port,
        path: options.path,
        method: options.method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...options.headers,
        },
      },
      (res) => {
        let rawData = "";
        res.on("data", (chunk) => {
          rawData += chunk;
        });
        res.on("end", () => {
          let parsed: any;
          try {
            parsed = JSON.parse(rawData);
          } catch {
            parsed = rawData;
          }
          resolve({ status: res.statusCode || 500, body: parsed });
        });
      }
    );

    req.on("error", reject);

    if (options.body) {
      req.write(JSON.stringify(options.body));
    }
    req.end();
  });
}

test("Gateway Routes Suite", async (t) => {
  let server: http.Server;
  const originalFetch = globalThis.fetch;

  t.beforeEach(() => {
    server = app.listen(0);
  });

  t.afterEach(() => {
    server.close();
    globalThis.fetch = originalFetch;
  });

  await t.test("POST /api/knowledge/index forwards to AI service", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = String(input);
      capturedMethod = init?.method || "GET";
      return new Response(
        JSON.stringify({
          success: true,
          indexed_files: 5,
          skipped_files: 2,
          removed_files: 0,
          failed_files: 0,
          indexed_chunks: 12,
          removed_chunks: 0,
          errors: {},
          message: "Indexing complete.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/knowledge/index",
    });

    assert.equal(res.status, 200);
    assert.equal(capturedMethod, "POST");
    assert.match(capturedUrl, /\/api\/knowledge\/index$/);
    assert.equal(res.body.success, true);
    assert.equal(res.body.indexed_files, 5);
  });

  await t.test("POST /api/memory/ forwards body and propagates 201 status", async () => {
    let capturedBody: any;

    globalThis.fetch = async (_input, init) => {
      capturedBody = JSON.parse(String(init?.body));
      return new Response(
        JSON.stringify({
          entry: { id: 1, summary: "Lesson 1" },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    };

    const payload = {
      category: "engineering_lesson",
      scope: "global",
      content: "Test lesson",
      summary: "Lesson 1",
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/memory/",
      body: payload,
    });

    assert.equal(res.status, 201);
    assert.equal(capturedBody.summary, "Lesson 1");
    assert.equal(res.body.entry.id, 1);
  });

  await t.test("GET /api/memory/ forwards query parameters", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(
        JSON.stringify({ total: 1, limit: 10, offset: 0, entries: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "GET",
      path: "/api/memory/?category=bug_fix&limit=10",
    });

    assert.equal(res.status, 200);
    assert.match(capturedUrl, /category=bug_fix/);
    assert.match(capturedUrl, /limit=10/);
  });

  await t.test("POST /api/agent/proposals/42/approve propagates 409 Conflict on tampering", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "Provided content_hash does not match proposal content." }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/agent/proposals/42/approve",
      body: { content_hash: "wrong_hash" },
    });

    assert.equal(res.status, 409);
    assert.match(res.body.detail, /Provided content_hash does not match/);
  });

  await t.test("Upstream network error returns 502 Bad Gateway safely", async () => {
    globalThis.fetch = async () => {
      throw new Error("connect ECONNREFUSED 127.0.0.1:8000");
    };

    const res = await makeRequest(server, {
      method: "GET",
      path: "/api/agent/git-status?project_root=/my/app",
    });

    assert.equal(res.status, 502);
    assert.equal(res.body.status, "error");
    assert.equal(res.body.error.code, "AI_SERVICE_UNAVAILABLE");
  });

  await t.test("Upstream timeout error returns 504 Gateway Timeout", async () => {
    globalThis.fetch = async () => {
      const timeoutErr = new Error("Request timed out");
      timeoutErr.name = "TimeoutError";
      throw timeoutErr;
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/knowledge/index",
    });

    assert.equal(res.status, 504);
    assert.equal(res.body.status, "error");
    assert.equal(res.body.error.code, "AI_SERVICE_TIMEOUT");
  });

  await t.test("GET /api/git/log forwards query parameters to AI service", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(
        JSON.stringify({ project_root: "/repo", total_returned: 1, entries: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "GET",
      path: "/api/git/log?project_root=/repo&max_count=5",
    });

    assert.equal(res.status, 200);
    assert.match(capturedUrl, /\/api\/git\/log\?project_root=\/repo&max_count=5/);
    assert.equal(res.body.total_returned, 1);
  });

  await t.test("POST /api/git/commit propagates 409 conflict when approval token invalid", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "Approval token mismatch." }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/git/commit",
      body: {
        project_root: "/repo",
        message: "feat: test",
        approval_token: "invalid",
      },
    });

    assert.equal(res.status, 409);
    assert.match(res.body.detail, /Approval token mismatch/);
  });

  await t.test("POST /api/chat forwards screen_context payload to AI service (Phase 14)", async () => {
    let capturedBody: any = null;

    globalThis.fetch = async (_input, init) => {
      if (init?.body) {
        capturedBody = JSON.parse(init.body as string);
      }
      return new Response(
        JSON.stringify({
          status: "success",
          source: "ai-service",
          message: "Understood screen content.",
          conversation_id: "conv-screen-1",
          meta: { screen_context_attached: true },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "POST",
      path: "/api/chat",
      body: {
        message: "What is on my screen?",
        screenContext: {
          user_granted_permission: true,
          window_title: "VS Code",
          image_base64: "dGVzdC1qcGVn",
        },
      },
    });

    assert.equal(res.status, 200);
    assert.equal(res.body.status, "success");
    assert.ok(capturedBody);
    assert.equal(capturedBody.screen_context?.user_granted_permission, true);
    assert.equal(capturedBody.screen_context?.window_title, "VS Code");
    assert.equal(capturedBody.screen_context?.image_base64, "dGVzdC1qcGVn");
  });

  await t.test("GET /api/observability/metrics forwards to AI service", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(
        JSON.stringify({
          status: "healthy",
          summary: { total_turns: 4, avg_turn_latency_ms: 120.5 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "GET",
      path: "/api/observability/metrics",
    });

    assert.equal(res.status, 200);
    assert.match(capturedUrl, /\/api\/observability\/metrics/);
    assert.equal(res.body.status, "healthy");
    assert.equal(res.body.summary.total_turns, 4);
  });

  await t.test("GET /api/observability/traces forwards query params", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (input) => {
      capturedUrl = String(input);
      return new Response(
        JSON.stringify({ count: 1, limit: 10, traces: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await makeRequest(server, {
      method: "GET",
      path: "/api/observability/traces?limit=10&outcome=success",
    });

    assert.equal(res.status, 200);
    assert.match(capturedUrl, /\/api\/observability\/traces\?limit=10&outcome=success/);
    assert.equal(res.body.count, 1);
  });
});

