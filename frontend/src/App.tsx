import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Reservations from './pages/Reservations';
import GuestSearch from './pages/GuestSearch';
import PerformanceTesting from './pages/PerformanceTesting';
import Settings from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/" element={<Reservations />} />
        <Route path="/guest-search" element={<GuestSearch />} />
        <Route path="/performance-testing" element={<PerformanceTesting />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;