/**
 * Observability & Telemetry Gateway Routes (Phase 16).
 *
 * Proxies telemetry metrics and audit traces to the Python AI service.
 */

import { Router, Request, Response } from "express";
import { forwardToAiService } from "./proxyHelper";

const router = Router();

// GET /api/observability/metrics — Aggregated turn latencies, tool call volume, and token estimates
router.get("/metrics", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/observability/metrics");
});

// GET /api/observability/traces — Audit log of individual tool executions
router.get("/traces", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/observability/traces");
});

export default router;
