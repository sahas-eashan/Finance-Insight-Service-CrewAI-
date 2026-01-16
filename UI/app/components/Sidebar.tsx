"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Icon, { type IconName } from "./Icon";
import { fetchThreads, type Thread } from "@/lib/api";

const primaryItems: {
  label: string;
  icon: IconName;
  href: string;
}[] = [
  { label: "New session", icon: "compose", href: "/?new=1" },
];

export default function Sidebar() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    const loadThreads = async () => {
      try {
        const data = await fetchThreads();
        console.log('Loaded threads:', data); // Debug log
        setThreads(data.slice(0, 15)); // Show last 15 conversations
      } catch (error) {
        console.error("Failed to load threads:", error);
        setThreads([]); // Clear threads on error
      } finally {
        setLoading(false);
      }
    };
    
    loadThreads();
    
    // Refresh threads every 10 seconds
    const interval = setInterval(loadThreads, 10000);
    return () => clearInterval(interval);
  }, [searchParams]); // Reload when URL params change

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2 className="sidebar-brand">Finance Insight</h2>
        <p className="sidebar-subtitle">AI Research Assistant</p>
      </div>
      
      <div className="sidebar-group">
        {primaryItems.map((item) => (
          <Link className="sidebar-item" href={item.href} key={item.label}>
            <span className="sidebar-icon">
              <Icon name={item.icon} />
            </span>
            <span className="sidebar-text">{item.label}</span>
          </Link>
        ))}
      </div>

      {threads.length > 0 && (
        <div className="sidebar-section">
          <p className="sidebar-label">Recent Chats</p>
          <div className="sidebar-threads">
            {threads.map((thread) => (
              <Link
                key={thread.id}
                href={`/?threadId=${thread.id}`}
                className="sidebar-thread"
                title={thread.title}
              >
                <span className="thread-icon">💬</span>
                <span className="thread-title">{thread.title}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="sidebar-section">
          <p className="sidebar-label">Loading...</p>
        </div>
      )}

      <div className="sidebar-footer">
        <Link className="sidebar-item sidebar-item--footer" href="/settings">
          <span className="sidebar-icon">
            <Icon name="sliders" />
          </span>
          <span className="sidebar-text">API &amp; Settings</span>
        </Link>
      </div>
    </aside>
  );
}
