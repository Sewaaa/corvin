import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import BreachMonitor from './pages/BreachMonitor';
import DomainReputation from './pages/DomainReputation';
import WebScanner from './pages/WebScanner';
import EmailProtection from './pages/EmailProtection';
import FileSandbox from './pages/FileSandbox';
import Notifications from './pages/Notifications';
import Reports from './pages/Reports';
import Settings from './pages/Settings';

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-corvin-900">
        <div className="animate-spin h-8 w-8 border-2 border-corvin-accent border-t-transparent rounded-full" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <SettingsProvider>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="breach" element={<BreachMonitor />} />
            <Route path="domain" element={<DomainReputation />} />
            <Route path="web-scan" element={<WebScanner />} />
            <Route path="email" element={<EmailProtection />} />
            <Route path="sandbox" element={<FileSandbox />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="reports" element={<Reports />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </SettingsProvider>
  );
}
