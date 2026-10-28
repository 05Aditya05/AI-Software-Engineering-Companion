/**
 * Knowledge gateway routes.
 *
 * Proxies project indexing and knowledge management requests to the Python AI service.
 */

import { Router, Request, Response } from "express";
import { forwardToAiService } from "./proxyHelper";

const router = Router();

// POST /api/knowledge/index — Trigger incremental project indexing
router.post("/index", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/knowledge/index");
});

export default router;
