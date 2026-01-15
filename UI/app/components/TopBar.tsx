import ThemeToggle from "./ThemeToggle";

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="brand-mark">S</div>
        <div className="topbar-title">Sentinel AI</div>
      </div>
      <div className="topbar-center">
        <span className="pill pill-muted">Agent Workspace</span>
      </div>
      <div className="topbar-right">
        <ThemeToggle />
        <div className="avatar">S</div>
      </div>
    </header>
  );
}
