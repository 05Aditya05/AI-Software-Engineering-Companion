/**
 * Health check API route for the frontend.
 *
 * Returns the frontend service status, version, and timestamps.
 * Useful for monitoring and verifying the frontend is running.
 */

import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "healthy",
    service: "ai-companion-frontend",
    version: "0.1.0",
    timestamp: new Date().toISOString(),
  });
}
