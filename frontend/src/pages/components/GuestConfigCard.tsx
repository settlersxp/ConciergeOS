import React, { useState, useCallback } from "react";
import type { TestGuest, GuestDetail } from "../../types";
import { Card, Button, Badge } from "../../components/ui";
import { performanceApi } from "../../services/api";

interface GuestConfigCardProps {
  guests: TestGuest[];
  sequentialBatchSize: number;
  loading: boolean;
  onSetupGuests: () => void;
  onRefreshList: () => void;
  onValidateGuests: () => void;
  validating: boolean;
}

export default function GuestConfigCard({
  guests,
  sequentialBatchSize,
  loading,
  onSetupGuests,
  onRefreshList,
  onValidateGuests,
  validating,
}: GuestConfigCardProps) {
  const expectedReservations = 4;

  const [expandedGuestId, setExpandedGuestId] = useState<number | null>(null);
  const [guestDetail, setGuestDetail] = useState<GuestDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const handleToggleRow = useCallback(
    async (guest: TestGuest) => {
      const targetId = guest.guest_id;

      // If already expanded, collapse
      if (expandedGuestId === targetId) {
        setExpandedGuestId(null);
        setGuestDetail(null);
        setDetailError(null);
        return;
      }

      // If another guest is expanded, collapse it first
      if (expandedGuestId !== null) {
        setExpandedGuestId(null);
        setGuestDetail(null);
        setDetailError(null);
      }

      // If we already have the detail cached, just show it
      if (guestDetail && guestDetail.guest_id === targetId) {
        setExpandedGuestId(targetId);
        return;
      }

      // Fetch guest detail
      setExpandedGuestId(targetId);
      setDetailLoading(true);
      setDetailError(null);

      try {
        const detail = await performanceApi.getGuestDetail(targetId);
        setGuestDetail(detail);
      } catch (err) {
        setDetailError(err instanceof Error ? err.message : "Failed to load guest details");
      } finally {
        setDetailLoading(false);
      }
    },
    [expandedGuestId, guestDetail],
  );

  return (
    <Card
      title="Test Guests Configuration"
      description="Create 13 test guests with exactly 4 reservations each to ensure constant LLM output and avoid caching effects."
    >
      <div className="flex gap-2 mb-4 flex-wrap">
        <Button variant="primary" loading={loading} onClick={onSetupGuests}>
          Setup 13 Test Guests
        </Button>
        <Button variant="secondary" loading={loading} onClick={onRefreshList}>
          Refresh List
        </Button>
        <Button variant="secondary" loading={validating} onClick={onValidateGuests} disabled={guests.length === 0}>
          Validate with LLM
        </Button>
      </div>

      {guests.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 dark:border-primary-700">
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-8">
                  #
                </th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400">
                  Guest Name
                </th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-24">
                  Reservations
                </th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-28">
                  Assignment
                </th>
              </tr>
            </thead>
            <tbody>
              {guests.map((g, i) => {
                const isSequential = i < sequentialBatchSize;
                const countOk = g.reservation_count === expectedReservations;
                const isExpanded = expandedGuestId === g.guest_id;

                return (
                  <React.Fragment key={g.guest_id}>
                    <tr
                      key={g.guest_id}
                      className={`border-b border-surface-100 dark:border-primary-700/50 cursor-pointer transition-colors ${
                        isExpanded
                          ? "bg-surface-200 dark:bg-primary-700/80"
                          : "hover:bg-surface-100 dark:hover:bg-primary-700/50"
                      }`}
                      onClick={() => handleToggleRow(g)}
                      title="Click to view details"
                    >
                      <td className="py-2 px-2 text-primary-500 dark:text-primary-400">
                        <span className="inline-flex items-center gap-1">
                          <span
                            className={`text-xs transition-transform ${
                              isExpanded ? "rotate-90" : ""
                            }`}
                          >
                            ▶
                          </span>
                          {i + 1}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-primary-800 dark:text-white font-medium">
                        {g.full_name}
                      </td>
                      <td className="py-2 px-2">
                        <Badge variant={countOk ? "success" : "neutral"}>
                          {g.reservation_count}
                        </Badge>
                      </td>
                      <td className="py-2 px-2">
                        <Badge variant={isSequential ? "neutral" : "danger"}>
                          {isSequential ? "Sequential" : "Concurrent"}
                        </Badge>
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {isExpanded && (
                      <tr key={`${g.guest_id}-detail`} className="bg-surface-50 dark:bg-primary-800/30">
                        <td colSpan={4} className="p-0">
                          <div className="w-full px-4 py-3">
                            {detailLoading && (
                              <div className="text-sm text-primary-500 dark:text-primary-400 italic">
                                Loading guest details...
                              </div>
                            )}
                            {detailError && (
                              <div className="text-sm text-red-500 dark:text-red-400">
                                {detailError}
                              </div>
                            )}
                            {guestDetail && !detailLoading && (
                              <pre className="w-full text-xs bg-white dark:bg-primary-900/50 border border-surface-200 dark:border-primary-700 rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap font-mono text-primary-700 dark:text-primary-300">
                                {JSON.stringify(guestDetail, null, 2)}
                              </pre>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}