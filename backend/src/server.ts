/**
 * HTTP server entry point.
 *
 * Starts the Express app on the configured port.
 * Handles graceful shutdown on SIGINT / SIGTERM.
 */

import app from "./app";
import { config } from "./config";

const server = app.listen(config.port, () => {
  console.log(`
+==================================================+
|   AI Software Engineering Companion -- Backend    |
+==================================================+
|   Status:  Running                                |
|   Port:    ${String(config.port).padEnd(37)}|
|   Env:     ${config.nodeEnv.padEnd(37)}|
|   Health:  http://localhost:${config.port}/api/health${" ".repeat(Math.max(0, 14 - String(config.port).length))}|
+==================================================+
  `);
});

// Graceful shutdown
const shutdown = (signal: string) => {
  console.log(`\n[${signal}] Shutting down gracefully...`);
  server.close(() => {
    console.log("Server closed.");
    process.exit(0);
  });
};

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
