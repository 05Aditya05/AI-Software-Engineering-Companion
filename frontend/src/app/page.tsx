"use client";

import { useState, useEffect, useRef, FormEvent } from "react";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  source?: string;
  conversationId?: string;
  meta?: Record<string, unknown>;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // WebSocket state
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [wsNote, setWsNote] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001";
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001/ws";

  // Auto-scroll to bottom of message list
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Establish WebSocket connection for real-time channel
  useEffect(() => {
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "pong") {
            setWsNote(`Heartbeat pong received at ${new Date(data.timestamp).toLocaleTimeString()}`);
          } else if (data.type === "connection") {
            setWsNote("Channel ready");
          }
        } catch {
          // ignore non-json messages
        }
      };

      ws.onerror = () => {
        setWsStatus("disconnected");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
      };
    } catch {
      setWsStatus("disconnected");
    }

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [wsUrl]);

  // Ping WebSocket channel
  const handlePingWs = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "ping" }));
      setWsNote("Ping sent...");
    } else {
      setWsNote("WebSocket not connected");
    }
  };

  // Send chat message via REST pipeline: Frontend -> Backend -> AI Service
  const handleSendMessage = async (e?: FormEvent, messageOverride?: string) => {
    if (e) e.preventDefault();

    const textToSend = (messageOverride !== undefined ? messageOverride : input).trim();
    if (!textToSend) {
      setError("Please enter a message before sending.");
      return;
    }

    setError(null);

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (messageOverride === undefined) {
      setInput("");
    }
    setIsLoading(true);

    try {
      const response = await fetch(`${backendUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: textToSend,
          conversationId: conversationId || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        let errorMsg = data?.error?.message;
        if (data?.error?.code === "LLM_RATE_LIMIT" || response.status === 429) {
          errorMsg =
            "Gemini API quota/rate limit exceeded. Please retry later or use another configured model/provider.";
        } else if (!errorMsg) {
          errorMsg = `Backend returned HTTP ${response.status}: ${response.statusText}`;
        }
        setError(errorMsg);
        return;
      }

      if (data?.status === "success" && data?.data) {
        const assistantMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          sender: "assistant",
          text: data.data.message,
          source: data.data.source,
          timestamp: new Date(data.data.timestamp).toLocaleTimeString(),
          conversationId: data.data.conversationId,
          meta: data.data.meta,
        };

        if (data.data.conversationId) {
          setConversationId(data.data.conversationId);
        }

        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        setError("Received an unexpected response payload from the backend.");
      }
    } catch (err: unknown) {
      const fetchError = err as Error;
      setError(
        `Failed to reach backend server at ${backendUrl}. Check that the Node.js backend is running. (${fetchError.message})`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
    setConversationId(null);
  };

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100 antialiased font-sans">
      {/* Top Navbar */}
      <header className="border-b border-zinc-800 bg-zinc-900/60 backdrop-blur px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center font-bold text-white shadow">
            AI
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              AI Software Engineering Companion
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                Phase 2
              </span>
            </h1>
            <p className="text-xs text-zinc-400">
              End-to-End Pipeline: Frontend ↔ Backend ↔ AI Service
            </p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-4 text-xs">
          {/* WebSocket Badge */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300">
            <span
              className={`h-2 w-2 rounded-full ${
                wsStatus === "connected"
                  ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"
                  : wsStatus === "connecting"
                  ? "bg-amber-500 animate-pulse"
                  : "bg-red-500"
              }`}
            />
            <span className="font-mono text-[11px]">
              WS: {wsStatus}
            </span>
            <button
              onClick={handlePingWs}
              title="Send WebSocket ping test"
              className="text-[10px] text-cyan-400 hover:underline ml-1"
            >
              Ping
            </button>
          </div>

          {wsNote && (
            <span className="text-[11px] text-zinc-400 hidden sm:inline font-mono">
              {wsNote}
            </span>
          )}

          {conversationId && (
            <span className="text-[11px] text-zinc-500 font-mono hidden md:inline">
              Session: {conversationId.slice(0, 15)}...
            </span>
          )}

          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded border border-zinc-800 hover:border-zinc-700"
            >
              Clear
            </button>
          )}
        </div>
      </header>

      {/* Chat Messages Body */}
      <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8 max-w-4xl w-full mx-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-6">
            <div className="max-w-md space-y-2">
              <div className="h-12 w-12 mx-auto rounded-xl bg-cyan-950/80 border border-cyan-800/50 flex items-center justify-center text-cyan-400 text-xl font-bold">
                ⚡
              </div>
              <h2 className="text-lg font-medium text-zinc-200">
                Phase 2 Communication Pipeline Ready
              </h2>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Messages typed here traverse from the Next.js frontend, through the
                Node.js backend proxy, to the Python FastAPI AI service, and return
                back with verified metadata.
              </p>
            </div>

            {/* Quick Test Prompt Chips */}
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {[
                "Hello companion!",
                "Verify communication pipeline",
                "Echo test with AI Service",
              ].map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleSendMessage(undefined, chip)}
                  disabled={isLoading}
                  className="text-xs bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg transition-colors text-left"
                >
                  &ldquo;{chip}&rdquo; &rarr;
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === "user" ? "items-end" : "items-start"
              }`}
            >
              <div className="flex items-center gap-2 mb-1 text-[11px] text-zinc-400 font-mono">
                <span>{msg.sender === "user" ? "You" : msg.source || "AI Service"}</span>
                <span>•</span>
                <span>{msg.timestamp}</span>
              </div>

              <div
                className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-cyan-600 text-white rounded-tr-sm"
                    : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-sm shadow-sm"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.text}</p>

                {msg.meta && (
                  <div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex flex-wrap gap-1.5 text-[10px] font-mono text-zinc-400">
                    <span className="bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 text-cyan-400">
                      source: {msg.source}
                    </span>
                    {msg.conversationId && (
                      <span className="bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800">
                        session: {msg.conversationId}
                      </span>
                    )}
                    <span className="bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 text-amber-400">
                      mock: true
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex flex-col items-start space-y-1">
            <div className="text-[11px] text-zinc-400 font-mono">AI Service • responding...</div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center space-x-2">
              <span className="h-2 w-2 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
              <span className="h-2 w-2 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
              <span className="h-2 w-2 bg-cyan-400 rounded-full animate-bounce" />
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-start gap-2.5">
            <span className="text-red-400 font-bold text-sm">⚠</span>
            <div className="flex-1">
              <p className="font-semibold mb-0.5">Error</p>
              <p>{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-200 text-xs font-mono"
            >
              ✕
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      {/* Message Input Footer */}
      <footer className="border-t border-zinc-800 bg-zinc-900/60 backdrop-blur p-4">
        <form
          onSubmit={(e) => handleSendMessage(e)}
          className="max-w-4xl mx-auto flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message to test the companion pipeline..."
            disabled={isLoading}
            className="flex-1 bg-zinc-950 border border-zinc-800 focus:border-cyan-500 focus:outline-none rounded-xl px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-sm px-5 py-2.5 rounded-xl transition-colors flex items-center gap-1.5"
          >
            {isLoading ? (
              <span>Sending...</span>
            ) : (
              <>
                <span>Send</span>
                <span className="text-xs">&rarr;</span>
              </>
            )}
          </button>
        </form>
      </footer>
    </div>
  );
}
