import React from 'react';
import type { Batch } from '../../types';

interface BatchListProps {
  batches: Batch[];
  onDeleteBatch: (uuid: string) => void;
}

export const BatchList: React.FC<BatchListProps> = ({ batches, onDeleteBatch }) => {
  if (batches.length === 0) return null;

  return (
    <div className="mb-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h3 className="mb-3 text-lg font-semibold text-gray-800">Batches</h3>
      <div className="space-y-2">
        {batches.map((b) => (
          <div key={b.batch_uuid} className="flex items-center justify-between rounded-md border border-gray-100 px-4 py-2">
            <div>
              <span className="font-medium text-sm text-gray-700">{b.friendly_name || b.batch_uuid.slice(0, 8)}</span>
              <span className="ml-3 text-xs text-gray-400">{b.total_requests} requests</span>
            </div>
            <button onClick={() => onDeleteBatch(b.batch_uuid)}
              className="text-xs text-red-500 hover:text-red-700">Delete</button>
          </div>
        ))}
      </div>
    </div>
  );
};