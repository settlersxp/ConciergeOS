import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { reservationsApi } from '../services/api';
import { useChainPagesContext } from '../context/ChainPagesContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MeResponse {
  roles: string[];
  menus: string[];
  error?: string;
}

// Mapping from menu identifiers (set in Keycloak role attributes) to
// the actual route paths used by React Router.
const MENU_TO_PATH: Record<string, string> = {
  reservations: '/',
  'performance-dashboard': '/performance-dashboard',
  prompts: '/prompts',
  'prompt-groups': '/prompt-groups',
  settings: '/settings',
};

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

async function fetchMe(): Promise<MeResponse> {
  const host = window.location.host;
  const resp = await fetch(`https://${host}/client-api/me`, {
    credentials: 'include',
  });
  if (!resp.ok) {
    return { roles: [], menus: [] };
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Header Component
// ---------------------------------------------------------------------------

export default function Header() {
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [menus, setMenus] = useState<string[]>([]);
  const context = useChainPagesContext();

  // Fetch allowed menus from the backend on mount.
  useEffect(() => {
    let cancelled = false;
    fetchMe().then((data) => {
      if (!cancelled) {
        if (data.error) {
          console.warn('[Header] /me error:', data.error);
        }
        // If no menus returned (e.g. not authenticated), show all.
        setMenus(data.menus.length > 0 ? data.menus : Object.keys(MENU_TO_PATH));
      }
    });
    return () => { cancelled = true; };
  }, []);

  const chainLinks = context?.chainPages
    .filter((p) => p.group.is_active)
    .map((p) => ({ path: p.route, label: p.group.name }))
    ?? [];

  // Build static links by filtering against the menus returned by /me.
  const allLinks = [
    { menu: 'reservations', path: '/', label: 'Reservations' },
    { menu: 'performance-dashboard', path: '/performance-dashboard', label: 'Dashboard' },
    { menu: 'prompts', path: '/prompts', label: 'Prompt Management' },
    { menu: 'prompt-groups', path: '/prompt-groups', label: 'Prompt Groups' },
    { menu: 'settings', path: '/settings', label: 'Settings' },
  ];

  const links = useMemo(
    () => allLinks.filter((l) => menus.includes(l.menu)),
    [menus],
  );

  const baseUrl = import.meta.env.BASE_URL;
  const currentApp = baseUrl === '/app2' ? 'app2' : 'app1';
  const otherApp = currentApp === 'app1' ? 'app2' : 'app1';
  const switchUrl = `https://${window.location.host}/${otherApp}`;

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

  const handleSwitchApp = () => {
    window.location.href = switchUrl;
  };

  const handleLogout = () => {
    const signOutUrl = `https://${window.location.host}/oauth2/sign_out`;
    window.location.href = signOutUrl;
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
                onClick={() => {
                  setDropdownOpen(!dropdownOpen);
                  setDebugOpen(false);
                }}
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
                      onClick={() => {
                        setDropdownOpen(false);
                        setDebugOpen(false);
                      }}
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

            {/* Debug Dropdown */}
            <div className="relative">
              <button
                onClick={() => {
                  setDebugOpen(!debugOpen);
                  setDropdownOpen(false);
                }}
                className="rounded-md px-3 py-2 text-sm text-yellow-300 transition-colors hover:bg-primary-800 hover:text-white flex items-center gap-1"
              >
                Debug
                <svg
                  className={`w-4 h-4 transition-transform ${debugOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {debugOpen && (
                <div className="absolute right-0 z-50 mt-1 min-w-[240px] rounded-md bg-primary-800 shadow-lg ring-1 ring-black/10 p-4 space-y-3">
                  <div className="text-sm">
                    <span className="text-primary-300">Base URL:</span>{' '}
                    <code className="bg-primary-900 px-1 rounded text-yellow-300">{baseUrl}</code>
                  </div>
                  <div className="text-sm">
                    <span className="text-primary-300">Current App:</span>{' '}
                    <code className="bg-primary-900 px-1 rounded text-yellow-300">{currentApp}</code>
                  </div>
                  <div className="text-sm">
                    <span className="text-primary-300">Menus:</span>{' '}
                    <code className="bg-primary-900 px-1 rounded text-yellow-300">
                      {menus.join(', ') || 'none'}
                    </code>
                  </div>
                  <button
                    onClick={handleSwitchApp}
                    className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                  >
                    Switch to {otherApp}
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
                  >
                    Logout
                  </button>
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