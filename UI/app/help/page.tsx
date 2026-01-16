import Link from "next/link";
import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function HelpPage() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="section-content">
          <div style={{ marginBottom: '20px' }}>
            <Link 
              href="/" 
              className="back-link"
            >
              <span style={{ fontSize: '18px' }}>←</span>
              Back to Chat
            </Link>
          </div>
          <SectionCard
            title="Help & Documentation"
            description="Finance Insight Service uses AI agents to research stocks, analyze market data, and provide evidence-backed insights. Ask about stocks, request technical indicators, or get news summaries with citations."
            actionLabel="Start chatting"
            actionHref="/"
          />
        </section>
      </main>
    </div>
  );
}
