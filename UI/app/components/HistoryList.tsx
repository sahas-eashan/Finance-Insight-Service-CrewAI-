"use client";

import { useRouter } from "next/navigation";
import AnimatedList from "./AnimatedList";

type HistoryListProps = {
  items: string[];
};

export default function HistoryList({ items }: HistoryListProps) {
  const router = useRouter();

  return (
    <div className="sidebar-history">
      <AnimatedList
        items={items}
        onItemSelect={(item) => {
          const label = typeof item === "string" ? item : item.label;
          router.push(`/history?title=${encodeURIComponent(label)}`);
        }}
        showGradients
        enableArrowNavigation
        displayScrollbar
        className="sidebar-animated-list"
        itemClassName="sidebar-animated-item"
      />
    </div>
  );
}
