"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ChatComposer from "./ChatComposer";
import ChatEmptyState from "./ChatEmptyState";
import { fetchHistory, sendMessage, type ChatMessage } from "@/lib/api";

type TraceEvent = {
  type?: string;
  agent?: string;
  task?: string;
  tool?: string;
  output?: any;
  summary?: string;
};

function TraceViewer({ events }: { events: TraceEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <div className="trace-viewer" onClick={(e) => e.stopPropagation()}>
        <div className="trace-header">🔍 Agent Execution Trace</div>
        <div className="trace-section">
          <div className="trace-content">
            <div className="trace-title">No trace events captured yet...</div>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="trace-viewer" onClick={(e) => e.stopPropagation()}>
      <div className="trace-header">🔍 Agent Execution Trace</div>
      {events.map((event, idx) => {
        if (event.type === "task_started") {
          return (
            <div key={idx} className="trace-section trace-task-start">
              <div className="trace-icon">📋</div>
              <div className="trace-content">
                <div className="trace-title">Task Started: {event.task}</div>
                {event.agent ? <div className="trace-agent">Agent: {event.agent}</div> : null}
              </div>
            </div>
          );
        }
        if (event.type === "task_completed") {
          return (
            <div key={idx} className="trace-section trace-task-complete">
              <div className="trace-icon">✅</div>
              <div className="trace-content">
                <div className="trace-title">Task Completed: {event.task}</div>
                {event.agent ? <div className="trace-agent">Agent: {event.agent}</div> : null}
                {event.output ? (
                  <details className="trace-output">
                    <summary>View Output</summary>
                    <pre>{event.output}</pre>
                  </details>
                ) : null}
              </div>
            </div>
          );
        }
        if (event.type === "task_failed") {
          return (
            <div key={idx} className="trace-section trace-task-failed">
              <div className="trace-icon">⚠️</div>
              <div className="trace-content">
                <div className="trace-title">Task Failed: {event.task}</div>
                {event.agent ? <div className="trace-agent">Agent: {event.agent}</div> : null}
              </div>
            </div>
          );
        }
        if (event.type === "tool_started") {
          return (
            <div key={idx} className="trace-section trace-tool">
              <div className="trace-icon">🔧</div>
              <div className="trace-content">
                <div className="trace-title">Using Tool: {event.tool}</div>
                {event.agent ? <div className="trace-detail">{event.agent}</div> : null}
              </div>
            </div>
          );
        }
        if (event.type === "tool_completed") {
          return (
            <div key={idx} className="trace-section trace-tool-done">
              <div className="trace-icon">✓</div>
              <div className="trace-content">
                <div className="trace-title">Tool Done: {event.tool}</div>
                {event.output?.status ? (
                  <div className="trace-detail">Status: {event.output.status}</div>
                ) : null}
              </div>
            </div>
          );
        }
        if (event.type === "tool_failed") {
          return (
            <div key={idx} className="trace-section trace-tool-failed">
              <div className="trace-icon">⚠️</div>
              <div className="trace-content">
                <div className="trace-title">Tool Failed: {event.tool}</div>
              </div>
            </div>
          );
        }
        if (event.type === "crew_started") {
          return (
            <div key={idx} className="trace-section trace-crew">
              <div className="trace-icon">🚀</div>
              <div className="trace-content">
                <div className="trace-title">Crew Execution Started</div>
              </div>
            </div>
          );
        }
        if (event.type === "crew_completed") {
          return (
            <div key={idx} className="trace-section trace-crew-done">
              <div className="trace-icon">🎉</div>
              <div className="trace-content">
                <div className="trace-title">Crew Execution Completed</div>
              </div>
            </div>
          );
        }
        if (event.type === "crew_failed") {
          return (
            <div key={idx} className="trace-section trace-crew-failed">
              <div className="trace-icon">⚠️</div>
              <div className="trace-content">
                <div className="trace-title">Crew Execution Failed</div>
              </div>
            </div>
          );
        }
        return (
          <div key={idx} className="trace-section">
            <div className="trace-icon">•</div>
            <div className="trace-content">
              <div className="trace-title">{event.summary || event.type}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const createLocalMessage = (role: ChatMessage["role"], content: string) => ({
  id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  role,
  content,
  createdAt: new Date().toISOString(),
});

const formatTime = (value?: string) => {
  if (!value) {
    return "";
  }

  try {
    return new Date(value).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
};

export default function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [skipHistory, setSkipHistory] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [currentTraces, setCurrentTraces] = useState<any[]>([]);
  const [liveMessages, setLiveMessages] = useState<string[]>([]);
  const router = useRouter();
  const searchParams = useSearchParams();
  const isNewSession = searchParams.get("new") === "1";
  const urlThreadId = searchParams.get("threadId");

  useEffect(() => {
    // Clear any prior trace state when switching threads
    setCurrentTraces([]);
    setShowTrace(false);
    setLiveMessages([]);
  }, [urlThreadId]);

  useEffect(() => {
    if (isNewSession) {
      setMessages([]);
      setThreadId(undefined);
      setError("");
      setIsLoading(false);
      setSkipHistory(true);
      router.replace("/", { scroll: false });
      return;
    }
    
    // Reset skipHistory when navigating to a specific thread
    if (urlThreadId) {
      setSkipHistory(false);
    }
  }, [isNewSession, router, urlThreadId]);

  useEffect(() => {
    if (isNewSession || skipHistory) {
      return;
    }

    const loadHistory = async () => {
      try {
        const history = await fetchHistory(urlThreadId || undefined);
        if (history.length) {
          setMessages(history);
          if (urlThreadId) {
            setThreadId(urlThreadId);
          }
        }
      } catch {
        setError("Unable to load history from the backend.");
      }
    };

    loadHistory();
  }, [isNewSession, skipHistory, urlThreadId]);

  const handleSend = async (content: string) => {
    if (!content.trim() || isLoading) {
      return;
    }

    setError("");
    setIsLoading(true);
    setShowTrace(false);
    setCurrentTraces([]);
    setLiveMessages([]);
    setMessages((prev) => [...prev, createLocalMessage("user", content)]);

    try {
      const response = await sendMessage(
        content,
        threadId,
        (message: string, detail: any) => {
          // Receive real-time trace updates
          setLiveMessages((prev) => [...prev, message]);
          setCurrentTraces((prev) => [...prev, detail]);
        }
      );
      
      if (response.threadId) {
        setThreadId(response.threadId);
      }

      // Store traces from response (ephemeral, only for this session)
      if (response.traces) {
        setCurrentTraces(response.traces);
      }

      if (response.messages?.length) {
        if (response.messages.length === 1) {
          setMessages((prev) => [...prev, response.messages[0]]);
        } else {
          setMessages(response.messages);
        }
      } else if (response.reply) {
        setMessages((prev) => [
          ...prev,
          createLocalMessage("assistant", response.reply || ""),
        ]);
      }
      
      // Clear live messages after completion
      setLiveMessages([]);
    } catch {
      setError("Message failed to send. Check your API settings.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTraceToggle = () => {
    console.log('Trace toggle clicked. Traces:', currentTraces.length, 'Current show:', showTrace);
    setShowTrace((prev) => !prev);
  };

  return (
    <div className={`chat-view ${messages.length ? "chat-view--has-messages" : ""}`}>
      {error ? <div className="banner banner-error">{error}</div> : null}
      <div className={`chat-scroll ${messages.length ? "" : "chat-scroll--empty"}`}>
        {messages.length ? (
          <div className="message-list">
            {messages.map((message) => {
              const isUser = message.role === "user";
              return (
                <div
                  className={`message ${isUser ? "message--user" : "message--assistant"}`}
                  key={message.id}
                >
                  <p>{message.content}</p>
                  {message.createdAt ? (
                    <span className="message-meta">{formatTime(message.createdAt)}</span>
                  ) : null}
                </div>
              );
            })}
            {isLoading ? (
              <div className="message message--assistant message--pending">
                <div className="thinking-container">
                  <button
                    type="button"
                    onClick={handleTraceToggle}
                    style={{ background: "none", border: "none", padding: 0, margin: 0, color: "inherit", cursor: "pointer", textDecoration: showTrace ? "underline" : "none" }}
                    aria-label="Show trace"
                  >
                    Thinking...
                  </button>
                  {liveMessages.length > 0 && (
                    <div className="live-trace-messages">
                      {liveMessages.slice(-3).map((msg, idx) => (
                        <div key={idx} className="live-trace-item">
                          {msg}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {showTrace && currentTraces.length > 0 ? (
                  <TraceViewer events={currentTraces} />
                ) : null}
              </div>
            ) : null}
            {!isLoading && currentTraces.length > 0 ? (
              <div className="trace-toggle-row">
                <button
                  type="button"
                  onClick={handleTraceToggle}
                  className="trace-toggle"
                  aria-label="Show trace"
                >
                  View trace
                </button>
                {showTrace ? <TraceViewer events={currentTraces} /> : null}
              </div>
            ) : null}
          </div>
        ) : (
          <ChatEmptyState />
        )}
      </div>
      <ChatComposer disabled={isLoading} onSend={handleSend} />
    </div>
  );
}
