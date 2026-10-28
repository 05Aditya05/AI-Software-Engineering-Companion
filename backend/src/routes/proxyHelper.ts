/**
 * Safe gateway proxy forwarder.
 *
 * Forwards requests to the configured AI service, propagating HTTP methods,
 * query parameters, JSON bodies, and HTTP status codes. Enforces timeouts
 * and catches network errors without leaking internal credentials.
 */

import { Request, Response } from "express";
import { config } from "../config";

export async function forwardToAiService(
  req: Request,
  res: Response,
  upstreamPath: string
): Promise<void> {
  const baseUrl = config.aiServiceUrl.replace(/\/+$/, "");
  
  // Extract query string from original request URL if present
  const queryIndex = req.url.indexOf("?");
  const queryString = queryIndex !== -1 ? req.url.slice(queryIndex) : "";
  const fullTargetUrl = `${baseUrl}${upstreamPath}${queryString}`;

  const fetchOptions: RequestInit = {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(config.aiServiceTimeoutMs),
  };

  if (req.method !== "GET" && req.method !== "HEAD" && req.body && Object.keys(req.body).length > 0) {
    fetchOptions.body = JSON.stringify(req.body);
  }

  try {
    const upstreamResponse = await fetch(fullTargetUrl, fetchOptions);

    let responseData: unknown;
    const contentType = upstreamResponse.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      responseData = await upstreamResponse.json();
    } else {
      const text = await upstreamResponse.text();
      responseData = { message: text };
    }

    res.status(upstreamResponse.status).json(responseData);
  } catch (err: unknown) {
    const error = err as Error;

    if (error.name === "TimeoutError" || error.name === "AbortError") {
      res.status(504).json({
        status: "error",
        error: {
          code: "AI_SERVICE_TIMEOUT",
          message: `AI service request timed out after ${config.aiServiceTimeoutMs}ms.`,
        },
      });
      return;
    }

    console.error(`[Gateway Proxy Error] ${req.method} ${fullTargetUrl}:`, error.message);
    res.status(502).json({
      status: "error",
      error: {
        code: "AI_SERVICE_UNAVAILABLE",
        message: "Failed to communicate with the AI service. Verify that the Python AI service is running.",
      },
    });
  }
}
