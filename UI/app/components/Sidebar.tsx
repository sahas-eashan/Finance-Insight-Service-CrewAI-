import Link from "next/link";
import HistoryList from "./HistoryList";
import Icon, { type IconName } from "./Icon";

const primaryItems: {
  label: string;
  icon: IconName;
  badge?: string;
  href: string;
}[] = [
  { label: "New session", icon: "compose", href: "/?new=1" },
  { label: "Search history", icon: "search", href: "/history" },
  { label: "Knowledge base", icon: "library", badge: "11", href: "/knowledge-base" },
  { label: "Agents", icon: "sparkles", href: "/agents" },
  { label: "Workflows", icon: "grid", href: "/workflows" },
];

const historyItems = [
  "Login troubleshooting",
  "Infrastructure summary",
  "Deployment checklist",
  "Access audit notes",
  "Weekly status update",
  "Incident analysis",
  "Patch planning",
  "Environment review",
  "Secrets rotation",
  "Automation ideas",
  "Monitoring tune-up",
  "Roadmap draft",
  "API documentation sync",
  "Security audit prep",
  "Backend optimization",
  "Database migration plan",
  "Frontend component audit",
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-group">
        {primaryItems.map((item) => (
          <Link className="sidebar-item" href={item.href} key={item.label}>
            <span className="sidebar-icon">
              <Icon name={item.icon} />
            </span>
            <span className="sidebar-text">{item.label}</span>
            {item.badge ? <span className="sidebar-badge">{item.badge}</span> : null}
          </Link>
        ))}
      </div>

      <div className="sidebar-section">
        <p className="sidebar-label">Workspace</p>
        <button className="sidebar-item" type="button">
          <span className="sidebar-avatar">S</span>
          <span className="sidebar-text">Sahas's Workspace</span>
        </button>
      </div>

      <div className="sidebar-section sidebar-section--chats">
        <p className="sidebar-label">History</p>
        <HistoryList items={historyItems} />
      </div>

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
