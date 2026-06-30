import React from "react";
import Card from "./Card";

export interface SummaryCardData {
  title: string;
  description: string;
  value: React.ReactNode;
}

interface SummaryCardGridProps {
  cards: SummaryCardData[];
  gridColumns?: number;
}

export default function SummaryCardGrid({
  cards,
  gridColumns,
}: SummaryCardGridProps) {
  if (cards.length === 0) return null;

  const gridStyle = gridColumns
    ? { gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))` }
    : undefined;

  return (
    <div className={`grid ${gridStyle ? "" : "grid-cols-2 sm:grid-cols-4"} gap-4`} style={gridStyle}>
      {cards.map((card, index) => (
        <Card key={index} title={card.title} description={card.description}>
          <div className="text-2xl font-mono font-bold text-primary-700 dark:text-primary-300">
            {card.value}
          </div>
        </Card>
      ))}
    </div>
  );
}