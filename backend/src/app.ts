/**
 * Express application setup.
 *
 * Configures middleware (CORS, JSON parsing, logging) and mounts routes.
 * Separated from server.ts so the app can be imported for testing
 * without starting the HTTP listener.
 */

import express from "express";
import cors from "cors";
import { config } from "./config";
import healthRouter from "./routes/health";
import chatRouter from "./routes/chat";

const app = express();

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

const allowedOrigins = [
  config.frontendUrl,
  "http://localhost:3000",
  "http://127.0.0.1:3000",
].filter(Boolean);

app.use(
  cors({
    origin: (origin, callback) => {
      // Allow non-browser requests (e.g. curl, tests, server-to-server) or matching origins
      if (!origin || allowedOrigins.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error(`Origin '${origin}' not allowed by CORS`));
      }
    },
    credentials: true,
  })
);

app.use(express.json({ limit: "10mb" }));

// Simple request logger (development only)
if (!config.isProduction) {
  app.use((req, _res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    next();
  });
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

app.get("/", (_req, res) => {
  res.json({
    name: "AI Software Engineering Companion — Backend",
    version: "0.1.0",
    docs: "/api/health",
  });
});

app.use("/api/health", healthRouter);
app.use("/api/chat", chatRouter);

// ---------------------------------------------------------------------------
// 404 handler
// ---------------------------------------------------------------------------

app.use((_req, res) => {
  res.status(404).json({
    status: "error",
    error: {
      code: "NOT_FOUND",
      message: "The requested endpoint was not found.",
    },
  });
});

// ---------------------------------------------------------------------------
// Central error handler (sanitizes internal errors & JSON parse failures)
// ---------------------------------------------------------------------------

app.use(
  (
    err: unknown,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction
  ): void => {
    // Catch malformed JSON syntax errors from express.json()
    if (err instanceof SyntaxError && "body" in err) {
      res.status(400).json({
        status: "error",
        error: {
          code: "INVALID_JSON",
          message: "Malformed JSON payload in request.",
        },
      });
      return;
    }

    console.error("[Backend Internal Error]:", err);
    res.status(500).json({
      status: "error",
      error: {
        code: "INTERNAL_SERVER_ERROR",
        message: "An unexpected server error occurred.",
      },
    });
  }
);

export default app;
