/**
 * Application configuration.
 *
 * Loads settings from environment variables with sensible defaults.
 * All configuration access should go through this module.
 */

import dotenv from "dotenv";

dotenv.config();

export const config = {
  /** Server port — defaults to 3001 to avoid conflicts with the frontend (3000). */
  port: parseInt(process.env.PORT || "3001", 10),

  /** Node environment */
  nodeEnv: process.env.NODE_ENV || "development",

  /** AI service base URL */
  aiServiceUrl: process.env.AI_SERVICE_URL || "http://localhost:8000",

  /** AI service request timeout in milliseconds (defaults to 60s for agentic tool loops) */
  aiServiceTimeoutMs: parseInt(process.env.AI_SERVICE_TIMEOUT_MS || "60000", 10),

  /** Frontend origin for CORS */
  frontendUrl: process.env.FRONTEND_URL || "http://localhost:3000",

  /** Whether we are running in production */
  isProduction: process.env.NODE_ENV === "production",
} as const;
