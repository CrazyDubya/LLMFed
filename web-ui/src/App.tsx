import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { GameProvider, useGame } from './context/GameContext';
import LoginPage from './pages/LoginPage';
import GameSetupPage from './pages/GameSetupPage';
import PromoterDashboard from './pages/PromoterDashboard';
import WrestlerDashboard from './pages/WrestlerDashboard';

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="min-h-screen bg-[#0f0f14] flex items-center justify-center text-gray-400">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return <>{children}</>;
}

function GameRoute() {
  const { playerType } = useGame();
  if (playerType === 'promoter') return <PromoterDashboard />;
  if (playerType === 'wrestler') return <WrestlerDashboard />;
  return <Navigate to="/setup" />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<ProtectedRoute><GameSetupPage /></ProtectedRoute>} />
      <Route path="/promoter" element={<ProtectedRoute><PromoterDashboard /></ProtectedRoute>} />
      <Route path="/wrestler" element={<ProtectedRoute><WrestlerDashboard /></ProtectedRoute>} />
      <Route path="/play" element={<ProtectedRoute><GameRoute /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/setup" />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <GameProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </GameProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
