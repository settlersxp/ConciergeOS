import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { reservationsApi } from '../services/api';
import { useChainPagesContext } from '../context/ChainPagesContext';

export default function Header() {
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const context = useChainPagesContext();

  const chainLinks = context?.chainPages
    .filter((p) => p.group.is_active)
    .map((p) => ({ path: p.route, label: p.group.name }))
    ?? [];

  // Static links only (no inline chain links)
  const links: { path: string; label: string }[] = [
    { path: '/', label: 'Reservations' },
    { path: '/performance-dashboard', label: 'Dashboard' },
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
          <nav className="relative flex items-center gap-1">
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

            {/* Workflows Dropdown */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="rounded-md px-3 py-2 text-sm text-primary-300 transition-colors hover:bg-primary-800 hover:text-white flex items-center gap-1"
              >
                Workflows
                <svg
                  className={`w-4 h-4 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {dropdownOpen && chainLinks.length > 0 && (
                <div className="absolute right-0 z-50 mt-1 min-w-[180px] rounded-md bg-primary-800 shadow-lg ring-1 ring-black/10">
                  {chainLinks.map((l) => (
                    <Link
                      key={l.path}
                      to={l.path}
                      onClick={() => setDropdownOpen(false)}
                      className={`block px-4 py-2 text-sm transition-colors ${
                        location.pathname === l.path
                          ? 'bg-primary-700 text-white'
                          : 'text-primary-200 hover:bg-primary-700 hover:text-white'
                      }`}
                    >
                      {l.label}
                    </Link>
                  ))}
                </div>
              )}
              {dropdownOpen && chainLinks.length === 0 && (
                <div className="absolute right-0 z-50 mt-1 min-w-[180px] rounded-md bg-primary-800 shadow-lg ring-1 ring-black/10 px-4 py-2 text-sm text-primary-400">
                  No workflows available
                </div>
              )}
            </div>
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