import React from 'react';
import type { TestGuest } from '../../types';

interface TestGuestsListProps {
  testGuests: TestGuest[];
}

export const TestGuestsList: React.FC<TestGuestsListProps> = ({ testGuests }) => {
  if (testGuests.length === 0) return null;

  return (
    <div className="mb-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h3 className="mb-3 text-lg font-semibold text-gray-800">Test Guests ({testGuests.length})</h3>
      <div className="grid gap-2 md:grid-cols-3">
        {testGuests.map((g) => (
          <div key={g.guest_id} className="rounded-md border border-gray-100 px-3 py-2 text-sm">
            <span className="font-medium text-gray-700">{g.full_name}</span>
            <span className="ml-2 text-xs text-gray-400">{g.reservation_count} reservations</span>
          </div>
        ))}
      </div>
    </div>
  );
};