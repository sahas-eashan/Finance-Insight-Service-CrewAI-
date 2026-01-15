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
          <SectionCard
            title="Help & Support"
            description="Find shortcuts, troubleshooting steps, and integration help."
            actionLabel="Open chat"
            actionHref="/"
          />
        </section>
      </main>
    </div>
  );
}
