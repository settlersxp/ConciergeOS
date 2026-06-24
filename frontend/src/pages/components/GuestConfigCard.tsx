import type { TestGuest } from "../../types";
import { Card, Button, Badge } from "../../components/ui";

interface GuestConfigCardProps {
  guests: TestGuest[];
  sequentialBatchSize: number;
  loading: boolean;
  onSetupGuests: () => void;
  onRefreshList: () => void;
}

export default function GuestConfigCard({
  guests,
  sequentialBatchSize,
  loading,
  onSetupGuests,
  onRefreshList,
}: GuestConfigCardProps) {
  const expectedReservations = 4;

  return (
    <Card
      title="Test Guests Configuration"
      description="Create 13 test guests with exactly 4 reservations each to ensure constant LLM output and avoid caching effects."
    >
      <div className="flex gap-2 mb-4">
        <Button variant="primary" loading={loading} onClick={onSetupGuests}>
          Setup 13 Test Guests
        </Button>
        <Button variant="secondary" loading={loading} onClick={onRefreshList}>
          Refresh List
        </Button>
      </div>

      {guests.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 dark:border-primary-700">
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-8">#</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400">Guest Name</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-24">Reservations</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-28">Assignment</th>
              </tr>
            </thead>
            <tbody>
              {guests.map((g, i) => {
                const isSequential = i < sequentialBatchSize;
                const countOk = g.reservation_count === expectedReservations;
                return (
                  <tr
                    key={g.guest_id}
                    className="border-b border-surface-100 dark:border-primary-700/50 hover:bg-surface-100 dark:hover:bg-primary-700/50"
                  >
                    <td className="py-2 px-2 text-primary-500 dark:text-primary-400">
                      {i + 1}
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
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}