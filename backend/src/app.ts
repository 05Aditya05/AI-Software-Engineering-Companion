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

const app = express();

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

app.use(
  cors({
    origin: config.frontendUrl,
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

// ---------------------------------------------------------------------------
// 404 handler
// ---------------------------------------------------------------------------

app.use((_req, res) => {
  res.status(404).json({ error: "Not found" });
});

export default app;
