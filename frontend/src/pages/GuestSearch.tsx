import { useState } from "react";
import { guestSearchApi } from "../services/api";
import type { GuestSearchResponse } from "../types";
import { PageHeader, Card, FormField, Input, Button, Toast } from "../components/ui";

export default function GuestSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuestSearchResponse | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) {
      setToast({ message: "Please enter a customer name", type: "error" });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const data = await guestSearchApi.search(query);
      setResult(data);
    } catch (e: unknown) {
      setToast({ message: e instanceof Error ? e.message : "Search failed", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="Guest Search"
        description="Search for guests using the LLM-powered query system."
      />

      <Card>
        <div className="mt-4">
          <FormField htmlFor="guestQuery" label="Customer Name">
            <Input
              id="guestQuery"
              type="text"
              placeholder="e.g. عائشة إبراهيم"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </FormField>
        </div>

        <div className="mt-4 flex justify-end">
          <Button variant="primary" loading={loading} onClick={handleSearch}>
            Search
          </Button>
        </div>
      </Card>

      {result && (
        <Card title="Search Result" className="mt-6">
          <div className="mt-4 whitespace-pre-wrap text-sm text-primary-800 dark:text-primary-200">
            {result.llm_response}
          </div>
        </Card>
      )}

      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}
    </div>
  );
}