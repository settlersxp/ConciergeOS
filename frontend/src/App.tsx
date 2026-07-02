import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Reservations from './pages/Reservations';
import GuestSearch from './pages/GuestSearch';
import PerformanceTesting from './pages/PerformanceTesting';
import Settings from './pages/Settings';
import PromptManagement from './pages/PromptManagement';
import PromptGroups from './pages/PromptGroups';
import PerformanceDashboard from './pages/PerformanceDashboard';
import PromptChainPage from './pages/PromptChainPage';
import { SettingsProvider } from './context/SettingsContext';
import { ChainPagesProvider } from './context/ChainPagesContext';
import { useChainPages } from './hooks/useChainPages';

function App() {
  const chainPagesData = useChainPages();

  return (
    <BrowserRouter>
      <SettingsProvider>
        <ChainPagesProvider
          chainPages={chainPagesData.chainPages}
          loading={chainPagesData.loading}
          findByRoute={chainPagesData.findByRoute}
        >
          <Header />
          <Routes>
            <Route path="/" element={<Reservations />} />
            <Route path="/guest-search" element={<GuestSearch />} />
            <Route path="/performance-testing" element={<PerformanceTesting />} />
            <Route path="/prompts" element={<PromptManagement />} />
            <Route path="/prompt-groups" element={<PromptGroups />} />
            <Route path="/performance-dashboard" element={<PerformanceDashboard />} />
            <Route path="/settings" element={<Settings />} />
            {/* Dynamically generated chain page routes */}
            {chainPagesData.chainPages.map((page) => (
              <Route key={page.route} path={page.route} element={<PromptChainPage />} />
            ))}
            {/* Fallback: legacy /prompt-chains/:route pattern */}
            <Route path="/prompt-chains/:route" element={<PromptChainPage />} />
          </Routes>
        </ChainPagesProvider>
      </SettingsProvider>
    </BrowserRouter>
  );
}

export default App;