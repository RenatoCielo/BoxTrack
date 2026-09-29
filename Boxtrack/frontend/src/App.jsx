import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { WorkspaceLayout } from './components/WorkspaceLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ResourcePage } from './pages/ResourcePage';
import { TrainingPage } from './pages/TrainingPage';
import { ReportsPage } from './pages/ReportsPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { StorePage } from './pages/StorePage';

function AppRoutes() {
  const { user, loading } = useAuth();
  const defaultPath = user?.role === 'ATHLETE' ? '/trainings' : '/dashboard';
  const role = user?.role;
  const canAccess = (roles) => roles.includes(role);

  if (loading) return <div className="page-loading">Cargando BOXTRACK...</div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={defaultPath} replace /> : <LoginPage />} />
      <Route element={user ? <WorkspaceLayout /> : <Navigate to="/login" replace />}>
        <Route path="/dashboard" element={canAccess(['ADMIN', 'TRAINER']) ? <DashboardPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/athletes" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="athletes" /> : <Navigate to="/trainings" replace />} />
        <Route path="/competitors" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="competitors" /> : <Navigate to="/trainings" replace />} />
        <Route path="/trainers" element={canAccess(['ADMIN']) ? <ResourcePage section="trainers" /> : <Navigate to="/trainings" replace />} />
        <Route path="/groups" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="groups" /> : <Navigate to="/trainings" replace />} />
        <Route path="/trainings" element={<TrainingPage />} />
        <Route path="/fights" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="fights" /> : <Navigate to="/trainings" replace />} />
        <Route path="/attendance" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="attendance" /> : <Navigate to="/trainings" replace />} />
        <Route path="/evaluations" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="evaluations" /> : <Navigate to="/trainings" replace />} />
        <Route path="/weight" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="weight" /> : <Navigate to="/trainings" replace />} />
        <Route path="/reports" element={canAccess(['ADMIN']) ? <ReportsPage /> : <Navigate to="/trainings" replace />} />
        <Route path="/alerts" element={canAccess(['ADMIN', 'TRAINER']) ? <ResourcePage section="alerts" /> : <Navigate to="/trainings" replace />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/store" element={<StorePage />} />
      </Route>
      <Route path="/" element={<Navigate to={user ? defaultPath : '/login'} replace />} />
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
