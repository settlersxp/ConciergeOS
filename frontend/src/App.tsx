import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Reservations from './pages/Reservations';
import GuestSearch from './pages/GuestSearch';
import PerformanceTesting from './pages/PerformanceTesting';
import Settings from './pages/Settings';
import PromptManagement from './pages/PromptManagement';
import PromptGroups from './pages/PromptGroups';
import PerformanceDashboard from './pages/PerformanceDashboard';
import { SettingsProvider } from './context/SettingsContext';

function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <Header />
        <Routes>
          <Route path="/" element={<Reservations />} />
          <Route path="/guest-search" element={<GuestSearch />} />
          <Route path="/performance-testing" element={<PerformanceTesting />} />
          <Route path="/prompts" element={<PromptManagement />} />
          <Route path="/prompt-groups" element={<PromptGroups />} />
          <Route path="/performance-dashboard" element={<PerformanceDashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </SettingsProvider>
    </BrowserRouter>
  );
}

export default App;