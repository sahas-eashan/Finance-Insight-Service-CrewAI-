export default function ChatEmptyState() {
  return (
    <div className="empty-state">
      <h1>What would you like to research?</h1>
      <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
        Ask about stocks, market analysis, or financial news.
      </p>
    </div>
  );
}
