import Link from "next/link";

type SectionCardProps = {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
};

export default function SectionCard({
  title,
  description,
  actionHref,
  actionLabel = "Back to chat",
}: SectionCardProps) {
  return (
    <div className="section-card">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="section-actions">
        <Link className="button-primary" href={actionHref ?? "/"}>
          {actionLabel}
        </Link>
      </div>
    </div>
  );
}
