/**
 * Controlled Coding Agent gateway routes.
 *
 * Proxies change proposals, diff retrieval, approval, application,
 * validation, and git status queries to the Python AI service.
 */

import { Router, Request, Response } from "express";
import { forwardToAiService } from "./proxyHelper";

const router = Router();

// POST /api/agent/proposals — Create a new change proposal
router.post("/proposals", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/agent/proposals");
});

// GET /api/agent/proposals — List proposals
router.get("/proposals", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/agent/proposals");
});

// GET /api/agent/proposals/:id — Get details of a single proposal
router.get("/proposals/:id", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/agent/proposals/${encodeURIComponent(String(id))}`);
});

// POST /api/agent/proposals/:id/approve — Approve a proposal (requires content_hash)
router.post("/proposals/:id/approve", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/agent/proposals/${encodeURIComponent(String(id))}/approve`);
});

// POST /api/agent/proposals/:id/reject — Reject a proposal
router.post("/proposals/:id/reject", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/agent/proposals/${encodeURIComponent(String(id))}/reject`);
});

// POST /api/agent/proposals/:id/apply — Apply approved proposal to filesystem
router.post("/proposals/:id/apply", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/agent/proposals/${encodeURIComponent(String(id))}/apply`);
});

// POST /api/agent/validate — Run allowlisted validation commands
router.post("/validate", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/agent/validate");
});

// GET /api/agent/git-status — Inspect git status
router.get("/git-status", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/agent/git-status");
});

export default router;
