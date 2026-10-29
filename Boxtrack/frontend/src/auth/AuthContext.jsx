import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

function getSavedTheme() {
  return localStorage.getItem('boxtrack.theme') === 'dark' ? 'dark' : 'light';
}

function validHex(value, fallback) {
  return /^#[0-9a-f]{6}$/i.test(value || '') ? value : fallback;
}

function contrastColor(hex) {
  const channels = hex.slice(1).match(/.{2}/g).map((part) => parseInt(part, 16) / 255);
  const luminance = channels.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
  return luminance > 0.42 ? '#161616' : '#ffffff';
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('boxtrack.user'));
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(Boolean(localStorage.getItem('boxtrack.access')));
  const [theme, setTheme] = useState(getSavedTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('boxtrack.theme', theme);
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    const primary = validHex(user?.club?.primary_color, '#b21f32');
    const accent = validHex(user?.club?.accent_color, '#151518');
    root.style.setProperty('--club-primary', primary);
    root.style.setProperty('--club-primary-contrast', contrastColor(primary));
    root.style.setProperty('--club-accent', accent);
    root.style.setProperty('--club-accent-contrast', contrastColor(accent));
  }, [user?.club?.primary_color, user?.club?.accent_color]);

  useEffect(() => {
    let active = true;
    const onExpired = () => {
      if (active) setUser(null);
    };
    window.addEventListener('boxtrack:session-expired', onExpired);

    if (localStorage.getItem('boxtrack.access')) {
      api.get('/auth/profile/')
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

  const updateProfile = async (values) => {
    const { data } = await api.patch('/auth/profile/', values);
    setUser(data);
    localStorage.setItem('boxtrack.user', JSON.stringify(data));
    return data;
  };

  const updateClub = (clubPatch) => {
    const updated = { ...user, club: { ...user?.club, ...clubPatch } };
    setUser(updated);
    localStorage.setItem('boxtrack.user', JSON.stringify(updated));
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
    <AuthContext.Provider value={{ user, loading, theme, setTheme, login, register, updateProfile, updateClub, changePassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
