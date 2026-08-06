import { useEffect, useState } from 'react';
import { reservationsApi } from '../services/api';
import type { ReservationsSummary } from '../types';
import { PageHeader, RoomCard, Badge, Card, Button } from '../components/ui';

export default function Reservations() {
  const [summary, setSummary] = useState<ReservationsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reservationsApi.getSummary();
      setSummary(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) return <div className="p-8 text-center text-primary-500">Loading reservations...</div>;
  if (error) return <div className="p-8 text-center text-accent-500">Error: {error}</div>;
  if (!summary) return null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader title="Reservations" description="View current hotel room reservations and guest status." />

      {/* Errors section */}
      {summary.errors.length > 0 && (
        <Card className="mb-8 border-accent-200 bg-accent-50 dark:border-accent-700 dark:bg-accent-900/20">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-lg font-semibold text-accent-700 dark:text-accent-300">
              Errors ({summary.errors.length})
            </div>
            <Button variant="danger" size="sm">View Details</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-accent-200 text-left text-primary-600 dark:border-accent-700 dark:text-primary-400">
                  <th className="py-2 pr-4">Room</th>
                  <th className="py-2 pr-4">Guest</th>
                  <th className="py-2 pr-4">Check In</th>
                  <th className="py-2 pr-4">Check Out</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2">Description</th>
                </tr>
              </thead>
              <tbody>
                {summary.errors.map((e) => (
                  <tr key={e.reservation_id} className="border-b border-accent-100 dark:border-accent-700/50">
                    <td className="py-2 pr-4 text-primary-800 dark:text-primary-200">{e.room_name}</td>
                    <td className="py-2 pr-4 text-primary-800 dark:text-primary-200">{e.guest_name}</td>
                    <td className="py-2 pr-4 text-primary-800 dark:text-primary-200">{e.check_in_date}</td>
                    <td className="py-2 pr-4 text-primary-800 dark:text-primary-200">{e.check_out_date}</td>
                    <td className="py-2 pr-4">
                      <Badge variant={e.error_type === 'conflict' ? 'danger' : 'warning'}>
                        {e.error_type}
                      </Badge>
                    </td>
                    <td className="py-2 text-primary-700 dark:text-primary-300">{e.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Rooms */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {Object.entries(summary.rooms).map(([roomName, reservations]) => (
          <RoomCard key={roomName} roomName={roomName}>
            {reservations.length === 0 ? (
              <p className="px-4 py-3 text-sm text-primary-400 dark:text-primary-500">No reservations</p>
            ) : (
              reservations.map((r) => (
                <div key={r.reservation_id} className="flex items-center justify-between px-4 py-2 text-sm">
                  <div>
                    <span className="font-medium text-primary-800 dark:text-primary-200">
                      {r.first_name} {r.last_name}
                    </span>
                    <span className="ml-2 text-xs text-primary-400 dark:text-primary-500">({r.status})</span>
                  </div>
                  <span className="text-primary-500 dark:text-primary-400">
                    {r.check_in_date} &rarr; {r.check_out_date}
                  </span>
                </div>
              ))
            )}
          </RoomCard>
        ))}
      </div>
    </div>
  );
}