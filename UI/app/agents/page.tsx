import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function AgentsPage() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="section-content">
          <SectionCard
            title="Agents"
            description="Manage and configure your CrewAI agent lineup."
            actionLabel="Open chat"
            actionHref="/"
          />
        </section>
      </main>
    </div>
  );
}
