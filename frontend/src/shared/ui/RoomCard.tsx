interface RoomCardProps {
  roomName: string;
  children: React.ReactNode;
  className?: string;
}

export default function RoomCard({ roomName, children, className = "" }: RoomCardProps) {
  return (
    <div className={`rounded-lg border border-surface-200 bg-surface-50 shadow-sm dark:border-primary-700 dark:bg-primary-800 ${className}`}>
      <div className="border-b border-surface-200 bg-surface-100 px-4 py-3 rounded-t-lg dark:border-primary-700 dark:bg-primary-900">
        <h3 className="font-semibold text-primary-900 dark:text-white">{roomName}</h3>
      </div>
      <div className="divide-y divide-surface-100 dark:divide-primary-700/50">
        {children}
      </div>
    </div>
  );
}