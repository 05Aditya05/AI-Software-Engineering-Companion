/**
 * Git Integration gateway routes (Phase 12).
 *
 * Proxies git inspection (log, diff, blame, branches, show) and
 * controlled mutation requests (stage, commit, branch) to the Python AI service.
 */

import { Router, Request, Response } from "express";
import { forwardToAiService } from "./proxyHelper";

const router = Router();

// GET /api/git/log — Recent commit history
router.get("/log", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/log");
});

// POST /api/git/diff — Diff query (working, staged, or refs)
router.post("/diff", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/diff");
});

// POST /api/git/blame — File blame annotations
router.post("/blame", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/blame");
});

// GET /api/git/branches — Branch listing
router.get("/branches", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/branches");
});

// POST /api/git/show — Show commit details
router.post("/show", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/show");
});

// POST /api/git/stage — Stage files
router.post("/stage", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/stage");
});

// POST /api/git/commit — Create commit with human approval token
router.post("/commit", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/commit");
});

// POST /api/git/branch — Create/switch branch
router.post("/branch", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/branch");
});

// GET /api/git/stage-token — Compute approval token for staged files + message
router.get("/stage-token", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/git/stage-token");
});

export default router;
