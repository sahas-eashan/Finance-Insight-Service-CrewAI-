import Link from "next/link";
import ChatView from "./components/ChatView";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Icon from "./components/Icon";

export default function Home() {
  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <section className="chat-content">
          <ChatView />
        </section>
        <Link className="help-button" href="/help" aria-label="Help">
          <Icon name="help" />
        </Link>
      </main>
    </div>
  );
}
