import { Link, useLocation } from 'react-router-dom';
import { reservationsApi } from '../services/api';

export default function Header() {
  const location = useLocation();
  const links: { path: string; label: string }[] = [
    { path: '/', label: 'Reservations' },
    { path: '/guest-search', label: 'Guest Search' },
    { path: '/performance-testing', label: 'Performance' },
    { path: '/performance-dashboard', label: 'Dashboard' },
    { path: '/prompt-chains/guest-intel', label: 'Guest Intelligence' },
    { path: '/prompt-chains/hello', label: 'Hello World' },
    { path: '/prompts', label: 'Prompt Management' },
    { path: '/prompt-groups', label: 'Prompt Groups' },
    { path: '/settings', label: 'Settings' },
  ];

  const handleShift = async () => {
    try {
      const data = await reservationsApi.shift(1);
      if (data.ok) {
        alert(`Shifted ${data.shifted} reservations by +1 day.`);
        window.location.reload();
      } else {
        alert(data.error || 'Shift failed.');
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert('Error shifting reservations: ' + msg);
    }
  };

  return (
    <header className="bg-primary-900 text-white shadow-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
        <h1 className="text-xl font-semibold">
          ConciergeOS{' '}
          <span className="text-primary-400 text-base">— Hotel Management</span>
        </h1>
        <div className="flex items-center gap-4">
          <nav className="flex gap-1">
            {links.map((l) => (
              <Link
                key={l.path}
                to={l.path}
                className={`rounded-md px-3 py-2 text-sm transition-colors ${
                  location.pathname === l.path
                    ? 'bg-primary-700 text-white'
                    : 'text-primary-300 hover:bg-primary-800 hover:text-white'
                }`}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <button
            onClick={handleShift}
            className="rounded-md bg-secondary-400 px-3 py-2 text-sm font-medium text-white hover:bg-secondary-500 transition-colors"
          >
            Shift +1 Day
          </button>
        </div>
      </div>
    </header>
  );
}