/**
 * Memory gateway routes.
 *
 * Proxies long-term memory CRUD operations to the Python AI service.
 */

import { Router, Request, Response } from "express";
import { forwardToAiService } from "./proxyHelper";

const router = Router();

// POST /api/memory/ — Create memory entry
router.post("/", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/memory/");
});

// GET /api/memory/ — List and search memories
router.get("/", async (req: Request, res: Response): Promise<void> => {
  await forwardToAiService(req, res, "/api/memory/");
});

// GET /api/memory/:id — Retrieve single memory entry
router.get("/:id", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/memory/${encodeURIComponent(String(id))}`);
});

// PATCH /api/memory/:id — Update memory entry
router.patch("/:id", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/memory/${encodeURIComponent(String(id))}`);
});

// DELETE /api/memory/:id — Delete memory entry
router.delete("/:id", async (req: Request, res: Response): Promise<void> => {
  const id = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  await forwardToAiService(req, res, `/api/memory/${encodeURIComponent(String(id))}`);
});

export default router;
