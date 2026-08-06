import React from "react";

interface ChartWithLegendProps {
  title: string;
  description: string;
  children: React.ReactNode;
  legend?: React.ReactNode;
  emptyMessage?: string;
}

export default function ChartWithLegend({
  children,
  legend,
  emptyMessage,
}: ChartWithLegendProps) {
  const isEmpty = !children;

  return (
    <div>
      {isEmpty ? (
        <p className="text-center py-12 text-sm text-primary-400">
          {emptyMessage || "No data available."}
        </p>
      ) : (
        <>
          {children}
          {legend && <div className="mt-3">{legend}</div>}
        </>
      )}
    </div>
  );
}