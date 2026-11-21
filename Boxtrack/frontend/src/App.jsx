import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { WorkspaceLayout } from './components/WorkspaceLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { GlobalAdminPage } from './pages/GlobalAdminPage';
import { ResourcePage } from './pages/ResourcePage';
import { FightsPage } from './pages/FightsPage';
import { TrainingPage } from './pages/TrainingPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { StorePage } from './pages/StorePage';
import { SettingsPage } from './pages/SettingsPage';
import { PublicHomePage } from './pages/PublicHomePage';
import { PublicClubPage } from './pages/PublicClubPage';
import { PlansPage } from './pages/PlansPage';
import { MembershipsPage } from './pages/MembershipsPage';

function AppRoutes() {
  const { user, loading } = useAuth();
  const defaultPath = user?.is_superuser ? '/global-admin' : user?.role === 'ATHLETE' ? '/trainings' : '/dashboard';
  const role = user?.is_superuser ? 'SUPERUSER' : user?.role;
  const canAccess = (roles) => roles.includes(role);

  if (loading) return <div className="page-loading">Cargando BOXTRACK...</div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={defaultPath} replace /> : <LoginPage />} />
      <Route path="/" element={user ? <Navigate to={defaultPath} replace /> : <PublicHomePage />} />
      <Route path="/gimnasios/:id" element={<PublicClubPage />} />
      <Route element={user ? <WorkspaceLayout /> : <Navigate to="/login" replace />}>
        <Route path="/dashboard" element={canAccess(['ADMIN', 'TRAINER']) ? <DashboardPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/global-admin" element={user?.is_superuser ? <GlobalAdminPage /> : <Navigate to={defaultPath} replace />} />
        <Route path="/athletes" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="athletes" /> : <Navigate to="/trainings" replace />} />
        <Route path="/competitors" element={<Navigate to="/athletes?profile=COMPETITORS" replace />} />
        <Route path="/trainers" element={canAccess(['ADMIN']) ? <ResourcePage section="trainers" /> : <Navigate to="/trainings" replace />} />
        <Route path="/trainings" element={!user?.is_superuser ? <TrainingPage /> : <Navigate to={defaultPath} replace />} />
        <Route path="/fights" element={canAccess(['ADMIN', 'TRAINER']) ? <FightsPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/fight-agreements" element={<Navigate to={user?.role === 'ADMIN' && !user?.is_superuser ? '/fights?tab=agreements' : '/fights'} replace />} />
        <Route path="/attendance" element={<Navigate to="/trainings" replace />} />
        <Route path="/alerts" element={<Navigate to="/notifications" replace />} />
        <Route path="/reports" element={<Navigate to="/dashboard" replace />} />
        <Route path="/notifications" element={!user?.is_superuser ? <NotificationsPage /> : <Navigate to={defaultPath} replace />} />
        <Route path="/store" element={!user?.is_superuser ? <StorePage /> : <Navigate to={defaultPath} replace />} />
        <Route path="/plans" element={user?.role === 'ADMIN' && user?.club ? <PlansPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/memberships" element={user?.role === 'ADMIN' && user?.club ? <MembershipsPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/settings" element={!user?.is_superuser ? <SettingsPage /> : <Navigate to={defaultPath} replace />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? defaultPath : '/login'} replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
