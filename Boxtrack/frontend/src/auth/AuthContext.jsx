import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('boxtrack.user'));
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(Boolean(localStorage.getItem('boxtrack.access')));

  useEffect(() => {
    let active = true;
    const onExpired = () => {
      if (active) setUser(null);
    };
    window.addEventListener('boxtrack:session-expired', onExpired);

    if (localStorage.getItem('boxtrack.access')) {
      api.get('/auth/me/')
        .then(({ data }) => {
          if (active) {
            setUser(data);
            localStorage.setItem('boxtrack.user', JSON.stringify(data));
          }
        })
        .catch(() => {
          if (active) setUser(null);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }

    return () => {
      active = false;
      window.removeEventListener('boxtrack:session-expired', onExpired);
    };
  }, []);

  const storeSession = (data) => {
    localStorage.setItem('boxtrack.access', data.tokens.access);
    localStorage.setItem('boxtrack.refresh', data.tokens.refresh);
    localStorage.setItem('boxtrack.user', JSON.stringify(data.user));
    setUser(data.user);
  };

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password });
    storeSession(data);
    return data.user;
  };

  const register = async (values) => {
    const { data } = await api.post('/auth/register/', values);
    storeSession(data);
    return data.user;
  };

  const changePassword = async (currentPassword, newPassword) => {
    await api.post('/auth/password/', {
      current_password: currentPassword,
      new_password: newPassword
    });
    const updatedUser = { ...user, must_change_password: false };
    setUser(updatedUser);
    localStorage.setItem('boxtrack.user', JSON.stringify(updatedUser));
  };

  const logout = () => {
    localStorage.removeItem('boxtrack.access');
    localStorage.removeItem('boxtrack.refresh');
    localStorage.removeItem('boxtrack.user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, changePassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}