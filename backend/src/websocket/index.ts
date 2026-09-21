/**
 * WebSocket server infrastructure.
 *
 * Provides the persistent real-time communication channel between the client
 * and the companion backend. In Phase 2, this establishes the foundational
 * connection lifecycle (connection, heartbeat/ping-pong, test echo).
 * In subsequent phases, this will stream LLM tokens, tool execution events,
 * and background agent notifications.
 */

import { Server as HttpServer } from "http";
import { WebSocketServer, WebSocket } from "ws";

interface InboundWsMessage {
  type?: string;
  payload?: unknown;
}

interface OutboundWsMessage {
  type: string;
  status?: string;
  payload?: unknown;
  timestamp: string;
}

export function setupWebSocket(server: HttpServer): WebSocketServer {
  const wss = new WebSocketServer({
    server,
    path: "/ws",
  });

  wss.on("connection", (ws: WebSocket, req) => {
    const clientIp = req.socket.remoteAddress || "unknown";
    console.log(`[WebSocket] Client connected from ${clientIp}`);

    // Send initial handshake confirmation
    const welcomePayload: OutboundWsMessage = {
      type: "connection",
      status: "connected",
      payload: {
        message: "AI Companion WebSocket channel ready for real-time streaming.",
        phase: "phase-2",
      },
      timestamp: new Date().toISOString(),
    };
    ws.send(JSON.stringify(welcomePayload));

    // Handle inbound messages
    ws.on("message", (data: string | Buffer) => {
      try {
        const rawString = data.toString();
        const parsed = JSON.parse(rawString) as InboundWsMessage;

        if (parsed.type === "ping") {
          const pongResponse: OutboundWsMessage = {
            type: "pong",
            timestamp: new Date().toISOString(),
          };
          ws.send(JSON.stringify(pongResponse));
          return;
        }

        if (parsed.type === "echo") {
          const echoResponse: OutboundWsMessage = {
            type: "echo",
            payload: parsed.payload,
            timestamp: new Date().toISOString(),
          };
          ws.send(JSON.stringify(echoResponse));
          return;
        }

        // Default unrecognized type acknowledgment
        const ackResponse: OutboundWsMessage = {
          type: "ack",
          payload: {
            receivedType: parsed.type || "unknown",
            note: "WebSocket infrastructure operational. Streaming will be enabled in Phase 4/5.",
          },
          timestamp: new Date().toISOString(),
        };
        ws.send(JSON.stringify(ackResponse));
      } catch (err) {
        console.error("[WebSocket] Failed to parse client message:", err);
        ws.send(
          JSON.stringify({
            type: "error",
            status: "error",
            payload: { message: "Invalid JSON format." },
            timestamp: new Date().toISOString(),
          })
        );
      }
    });

    ws.on("error", (err) => {
      console.error(`[WebSocket] Client error (${clientIp}):`, err.message);
    });

    ws.on("close", (code, reason) => {
      console.log(
        `[WebSocket] Client disconnected (${clientIp}), code: ${code}, reason: ${reason.toString()}`
      );
    });
  });

  return wss;
}
