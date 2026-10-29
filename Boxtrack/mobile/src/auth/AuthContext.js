import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { tokenStorage } from '../api/storage';
import { applyClubBranding } from '../theme';

const AuthContext = createContext(null);

// status: loading | signedOut | signedIn | offline
export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading');
  const [user, setUser] = useState(null);
  const [notice, setNotice] = useState('');

  const bootstrap = useCallback(async () => {
    setStatus('loading');
    const token = await tokenStorage.getAccess();
    if (!token) {
      applyClubBranding(null);
      setStatus('signedOut');
      return;
    }
    try {
      const profile = await api.get('/auth/profile/');
      applyClubBranding(profile.club);
      setUser(profile);
      setStatus('signedIn');
    } catch (error) {
      if (error.isNetwork) {
        setStatus('offline');
      } else {
        await tokenStorage.clear();
        applyClubBranding(null);
        setUser(null);
        setStatus('signedOut');
      }
    }
  }, []);

  useEffect(() => {
    api.setSessionExpiredHandler(() => {
      applyClubBranding(null);
      setUser(null);
      setNotice('Tu sesión expiró. Inicia sesión nuevamente.');
      setStatus('signedOut');
    });
    bootstrap();
    return () => api.setSessionExpiredHandler(null);
  }, [bootstrap]);

  const login = useCallback(async (username, password) => {
    const data = await api.post('/auth/login/', { username: username.trim(), password });
    await tokenStorage.save(data.tokens);
    applyClubBranding(data.user.club);
    setNotice('');
    setUser(data.user);
    setStatus('signedIn');
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    await tokenStorage.clear();
    applyClubBranding(null);
    setUser(null);
    setNotice('');
    setStatus('signedOut');
  }, []);

  const refreshUser = useCallback(async () => {
    const data = await api.get('/auth/profile/');
    applyClubBranding(data.club);
    setUser(data);
    return data;
  }, []);

  const updateProfile = useCallback(async (values) => {
    const data = await api.patch('/auth/profile/', values);
    applyClubBranding(data.club);
    setUser(data);
    return data;
  }, []);

  const value = useMemo(
    () => ({ status, user, notice, login, logout, refreshUser, updateProfile, retry: bootstrap }),
    [status, user, notice, login, logout, refreshUser, updateProfile, bootstrap]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return value;
}

export const isStaff = (user) => user?.role === 'ADMIN' || user?.role === 'TRAINER';
export const clubId = (user) => (typeof user?.club === 'object' ? user.club?.id : user?.club);
