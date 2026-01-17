import ThemeToggle from "./ThemeToggle";

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Empty - brand is in sidebar */}
      </div>
      <div className="topbar-center">
        <span className="pill pill-muted">Research Assistant</span>
      </div>
      <div className="topbar-right">
        <ThemeToggle />
      </div>
    </header>
  );
}
