/**
 * Chat routes.
 *
 * Exposes REST endpoints for chatting with the AI companion.
 * In Phase 2, this validates incoming messages and proxies requests
 * to the Python AI service, handling timeouts, connection failures,
 * and malformed responses safely.
 */

import { Router, Request, Response } from "express";
import { config } from "../config";

const router = Router();

interface ChatRequestBody {
  message?: unknown;
  conversationId?: unknown;
  conversation_id?: unknown;
}

interface ChatSuccessResponse {
  status: "success";
  data: {
    message: string;
    source: string;
    conversationId: string;
    timestamp: string;
    meta?: Record<string, unknown>;
  };
}

interface ChatErrorResponse {
  status: "error";
  error: {
    code: string;
    message: string;
  };
}

router.post("/", async (req: Request, res: Response): Promise<void> => {
  const body = req.body as ChatRequestBody;

  // 1. Validation: body must be provided
  if (!body || typeof body !== "object") {
    res.status(400).json({
      status: "error",
      error: {
        code: "INVALID_REQUEST_BODY",
        message: "Request body must be a valid JSON object.",
      },
    } satisfies ChatErrorResponse);
    return;
  }

  // 2. Validation: message must be a non-empty string
  if (typeof body.message !== "string" || body.message.trim().length === 0) {
    res.status(400).json({
      status: "error",
      error: {
        code: "INVALID_MESSAGE",
        message: "Field 'message' is required and must be a non-empty string.",
      },
    } satisfies ChatErrorResponse);
    return;
  }

  const cleanedMessage = body.message.trim();

  // 3. Validation: conversationId if provided must be a string
  const rawConvId = body.conversationId ?? body.conversation_id;
  let activeConversationId: string | undefined = undefined;
  if (rawConvId !== undefined && rawConvId !== null) {
    if (typeof rawConvId !== "string" || rawConvId.trim().length === 0) {
      res.status(400).json({
        status: "error",
        error: {
          code: "INVALID_CONVERSATION_ID",
          message: "Field 'conversationId' must be a non-empty string if provided.",
        },
      } satisfies ChatErrorResponse);
      return;
    }
    activeConversationId = rawConvId.trim();
  }

  // 4. Proxy to AI Service
  const targetUrl = `${config.aiServiceUrl.replace(/\/+$/, "")}/api/chat/`;

  try {
    const aiServiceResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        message: cleanedMessage,
        conversation_id: activeConversationId,
      }),
      signal: AbortSignal.timeout(config.aiServiceTimeoutMs),
    });

    if (!aiServiceResponse.ok) {
      console.error(
        `[Backend -> AI Service] Received HTTP ${aiServiceResponse.status} from ${targetUrl}`
      );
      res.status(502).json({
        status: "error",
        error: {
          code: "AI_SERVICE_ERROR",
          message: `AI service returned error status ${aiServiceResponse.status}.`,
        },
      } satisfies ChatErrorResponse);
      return;
    }

    const aiData = (await aiServiceResponse.json()) as {
      message?: string;
      source?: string;
      conversation_id?: string;
      timestamp?: string;
      meta?: Record<string, unknown>;
    };

    if (!aiData || typeof aiData.message !== "string") {
      res.status(502).json({
        status: "error",
        error: {
          code: "MALFORMED_AI_RESPONSE",
          message: "AI service returned an unexpected response structure.",
        },
      } satisfies ChatErrorResponse);
      return;
    }

    res.status(200).json({
      status: "success",
      data: {
        message: aiData.message,
        source: aiData.source || "ai-service",
        conversationId: aiData.conversation_id || activeConversationId || "unknown",
        timestamp: aiData.timestamp || new Date().toISOString(),
        meta: aiData.meta,
      },
    } satisfies ChatSuccessResponse);
  } catch (err: unknown) {
    const error = err as Error;

    if (error.name === "TimeoutError" || error.name === "AbortError") {
      console.error(`[Backend -> AI Service] Request timed out after ${config.aiServiceTimeoutMs}ms`);
      res.status(504).json({
        status: "error",
        error: {
          code: "GATEWAY_TIMEOUT",
          message: `AI service request timed out after ${config.aiServiceTimeoutMs}ms.`,
        },
      } satisfies ChatErrorResponse);
      return;
    }

    // Connection refused / network failure
    console.error(`[Backend -> AI Service] Failed to reach AI service:`, error.message);
    res.status(502).json({
      status: "error",
      error: {
        code: "AI_SERVICE_UNAVAILABLE",
        message: "AI service is currently unreachable. Please verify that the AI service is running.",
      },
    } satisfies ChatErrorResponse);
  }
});

export default router;
