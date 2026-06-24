import type { SummaryData } from "../../types";

interface SummaryCardsProps {
  data: SummaryData;
}

const cards = [
  {
    key: "total" as const,
    label: "Total Requests",
    color: "text-primary-600 dark:text-primary-400",
  },
  {
    key: "avg" as const,
    label: "Avg Response Time",
    color: "text-secondary-400 dark:text-secondary-300",
  },
  {
    key: "min" as const,
    label: "Min Response Time",
    color: "text-accent-400 dark:text-accent-300",
  },
  {
    key: "max" as const,
    label: "Max Response Time",
    color: "text-accent-600 dark:text-accent-400",
  },
];

export default function SummaryCards({ data }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-6">
      {cards.map((card) => (
        <div
          key={card.key}
          className="bg-surface-50 dark:bg-primary-800 rounded-lg border border-surface-200 dark:border-primary-700 p-4"
        >
          <div className={`text-2xl font-bold ${card.color}`}>
            {card.key === "total" ? data.total : data[card.key]}
          </div>
          <div className="text-xs text-primary-500 dark:text-primary-400 mt-1">
            {card.label}
          </div>
        </div>
      ))}
      {data.model && (
        <div className="bg-surface-50 dark:bg-primary-800 rounded-lg border border-surface-200 dark:border-primary-700 p-4">
          <div className="text-2xl font-bold text-primary-700 dark:text-primary-300 truncate">
            {data.model}
          </div>
          <div className="text-xs text-primary-500 dark:text-primary-400 mt-1">
            Model
          </div>
        </div>
      )}
    </div>
  );
}