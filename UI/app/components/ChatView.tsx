"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ChatComposer from "./ChatComposer";
import ChatEmptyState from "./ChatEmptyState";
import { fetchHistory, sendMessage, type ChatMessage } from "@/lib/api";

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
  const router = useRouter();
  const searchParams = useSearchParams();
  const isNewSession = searchParams.get("new") === "1";

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
  }, [isNewSession, router]);

  useEffect(() => {
    if (isNewSession || skipHistory) {
      return;
    }

    const loadHistory = async () => {
      try {
        const history = await fetchHistory();
        if (history.length) {
          setMessages(history);
        }
      } catch {
        setError("Unable to load history from the backend.");
      }
    };

    loadHistory();
  }, [isNewSession, skipHistory]);

  const handleSend = async (content: string) => {
    if (!content.trim() || isLoading) {
      return;
    }

    setError("");
    setIsLoading(true);
    setMessages((prev) => [...prev, createLocalMessage("user", content)]);

    try {
      const response = await sendMessage(content, threadId);
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
    } catch {
      setError("Message failed to send. Check your API settings.");
    } finally {
      setIsLoading(false);
    }
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
                Thinking...
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
