/**
 * Health check route.
 *
 * Provides a simple endpoint to verify the backend service is running.
 * Used by the frontend, monitoring, and service orchestration.
 */

import { Router, Request, Response } from "express";

const router = Router();

router.get("/", (_req: Request, res: Response) => {
  res.json({
    status: "healthy",
    service: "ai-companion-backend",
    version: "0.1.0",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

export default router;
