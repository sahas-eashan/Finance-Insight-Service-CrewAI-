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

export default function HistoryPage({ searchParams }: HistoryPageProps) {
  const selectedTitle = resolveTitle(searchParams?.title);
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
          <SectionCard title={title} description={description} />
        </section>
      </main>
    </div>
  );
}
