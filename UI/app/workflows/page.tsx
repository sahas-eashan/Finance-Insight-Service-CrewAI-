import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function WorkflowsPage() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="section-content">
          <SectionCard
            title="Workflows"
            description="Build multi-step automations for your agents."
            actionLabel="Open chat"
            actionHref="/"
          />
        </section>
      </main>
    </div>
  );
}
