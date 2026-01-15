import SettingsForm from "../components/SettingsForm";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function SettingsPage() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="settings-content">
          <SettingsForm />
        </section>
      </main>
    </div>
  );
}
