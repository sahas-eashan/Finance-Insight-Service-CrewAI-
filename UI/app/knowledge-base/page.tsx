import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function KnowledgeBasePage() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="section-content">
          <SectionCard
            title="Knowledge Base"
            description="Upload and manage documents for your agents to use."
            actionLabel="Open chat"
            actionHref="/"
          />
        </section>
      </main>
    </div>
  );
}
