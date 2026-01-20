"use client";

import { useRef, useState } from "react";
import ChatComposer from "./ChatComposer";
import ChatEmptyState from "./ChatEmptyState";
import TopBar from "./TopBar";
import { cancelJob, sendMessage, type ChatMessage } from "@/lib/api";
import React from "react";

const formatMessageContent = (content: string) => {
  const hasLimitations = content.includes("Limitations:");
  const hasSources = content.includes("Sources:") || content.includes("sources:");

  if (hasLimitations || hasSources) {
    let mainContent = content;
    let additionalDetails = "";

    const limitationsMatch = content.match(
      /(Limitations:|Sources:|References:|Note:|Disclaimer:)[\s\S]*/i,
    );
    if (limitationsMatch) {
      mainContent = content.substring(0, limitationsMatch.index).trim();
      additionalDetails = limitationsMatch[0].trim();
    }

    return { mainContent, additionalDetails, hasDetails: !!additionalDetails };
  }

  return { mainContent: content, additionalDetails: "", hasDetails: false };
};

function MessageContent({ content }: { content: string }) {
  const [showDetails, setShowDetails] = React.useState(false);
  const formatted = formatMessageContent(content);

  return (
    <>
      <div className="message-main-content">{formatted.mainContent}</div>
      {formatted.hasDetails ? (
        <div className="message-details">
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="message-details-toggle"
          >
            {showDetails ? "Hide details" : "More info"}
          </button>
          {showDetails ? (
            <div className="message-details-content">
              {formatted.additionalDetails}
            </div>
          ) : null}
        </div>
      ) : null}
    </>
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
  const [liveMessages, setLiveMessages] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const cancelInFlight = () => {
    if (!isLoading) {
      return;
    }
    try {
      abortRef.current?.abort();
    } catch {
      // Ignore abort errors from browsers that throw on aborted signals.
    }
    if (jobIdRef.current) {
      void cancelJob(jobIdRef.current);
    }
    setIsLoading(false);
    setLiveMessages([]);
    setError("");
  };

  const handleNewChat = () => {
    cancelInFlight();
    setMessages([]);
    setThreadId(undefined);
    setError("");
    setLiveMessages([]);
  };

  const handleSend = async (content: string) => {
    if (!content.trim() || isLoading) {
      return;
    }

    setError("");
    setIsLoading(true);
    setLiveMessages([]);
    setMessages((prev) => [...prev, createLocalMessage("user", content)]);
    const abortController = new AbortController();
    abortRef.current = abortController;
    jobIdRef.current = null;

    try {
      const response = await sendMessage(content, threadId, {
        onTrace: (message: string) => {
          setLiveMessages((prev) => [...prev, message]);
        },
        onJobId: (jobId) => {
          jobIdRef.current = jobId;
        },
        signal: abortController.signal,
      });

      if (response.threadId) {
        setThreadId(response.threadId);
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

      setLiveMessages([]);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const errorMsg = err instanceof Error ? err.message : "Message failed to send";
      if (errorMsg.includes("Cannot connect")) {
        setError("Cannot connect to API server. Please check if the backend is running.");
      } else if (errorMsg.toLowerCase().includes("cancelled")) {
        setError("");
      } else {
        setError(errorMsg);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
      jobIdRef.current = null;
    }
  };

  return (
    <main className="chat-main">
      <TopBar onNewChat={handleNewChat} />
      <section className="chat-content">
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
                      {isUser ? <p>{message.content}</p> : <MessageContent content={message.content} />}
                      {message.createdAt ? (
                        <span className="message-meta">{formatTime(message.createdAt)}</span>
                      ) : null}
                    </div>
                  );
                })}
                {isLoading ? (
                  <div className="thinking-container">
                    <span className="thinking-text">Thinking...</span>
                    {liveMessages.length > 0 ? (
                      <div className="live-trace-messages">
                        {liveMessages.slice(-5).map((msg, idx) => (
                          <div key={idx} className="live-trace-item">
                            {msg}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <ChatEmptyState onSelectScenario={handleSend} />
            )}
          </div>
          <ChatComposer
            disabled={isLoading}
            loading={isLoading}
            onSend={handleSend}
            onStop={cancelInFlight}
          />
        </div>
      </section>
    </main>
  );
}
