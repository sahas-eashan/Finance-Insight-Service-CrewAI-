import Link from "next/link";
import SectionCard from "../components/SectionCard";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

type HistoryPageProps = {
  searchParams?: {
    title?: string | string[];
  };
};

const resolveTitle = (title?: string | string[]) => {
  if (!title) {
    return "";
  }
  return Array.isArray(title) ? title[0] : title;
};

export default async function HistoryPage({ searchParams }: HistoryPageProps) {
  const params = await searchParams;
  const selectedTitle = resolveTitle(params?.title);
  const title = selectedTitle ? `History: ${selectedTitle}` : "History";
  const description = selectedTitle
    ? "Review this conversation or restart it in the main chat."
    : "Browse your recent sessions and revisit agent outputs.";

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
          <SectionCard title={title} description={description} />
        </section>
      </main>
    </div>
  );
}
