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

interface TokenClaimsResponse {
  claims: Record<string, unknown>;
  raw_headers: Record<string, string>;
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

async function fetchTokenClaims(): Promise<TokenClaimsResponse> {
  const host = window.location.host;
  const resp = await fetch(`https://${host}/client-api/me/token-claims`, {
    credentials: 'include',
  });
  if (!resp.ok) {
    return { claims: {}, raw_headers: {} };
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
  const [tokenClaims, setTokenClaims] = useState<TokenClaimsResponse | null>(null);
  const [claimsExpanded, setClaimsExpanded] = useState(false);
  const context = useChainPagesContext();

  // Fetch allowed menus and token claims from the backend on mount.
  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMe(), fetchTokenClaims()]).then(([meData, claimsData]) => {
      if (!cancelled) {
        if (meData.error) {
          console.warn('[Header] /me error:', meData.error);
        }
        // If no menus returned (e.g. not authenticated), show all.
        setMenus(meData.menus.length > 0 ? meData.menus : Object.keys(MENU_TO_PATH));
        setTokenClaims(claimsData);
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

  const currentApp = window.location.pathname.startsWith('/app2') ? 'app2' : 'app1';
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
                <div className="absolute right-0 z-50 mt-1 min-w-[280px] rounded-md bg-primary-800 shadow-lg ring-1 ring-black/10 p-4 space-y-3">
                  <div className="text-sm">
                    <span className="text-primary-300">Path:</span>{' '}
                    <code className="bg-primary-900 px-1 rounded text-yellow-300">{window.location.pathname}</code>
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

                  {/* JWT Claims Section */}
                  {tokenClaims && Object.keys(tokenClaims.claims).length > 0 && (
                    <div className="border-t border-primary-700 pt-3 space-y-2">
                      <button
                        onClick={() => setClaimsExpanded(!claimsExpanded)}
                        className="w-full flex items-center justify-between text-sm text-yellow-300 hover:text-yellow-200 transition-colors"
                      >
                        <span>
                          <span className="text-primary-300">JWT Claims:</span> Keycloak Token Info
                        </span>
                        <svg
                          className={`w-4 h-4 transition-transform ${claimsExpanded ? 'rotate-180' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                      {claimsExpanded && (
                        <div className="bg-primary-900 rounded p-2 max-h-80 overflow-auto">
                          <pre className="text-xs text-yellow-300 whitespace-pre-wrap font-mono">
                            {JSON.stringify(tokenClaims.claims, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="border-t border-primary-700 pt-3 space-y-2">
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