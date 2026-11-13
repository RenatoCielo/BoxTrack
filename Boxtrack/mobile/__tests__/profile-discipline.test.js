import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import ProfileScreen from '../src/screens/ProfileScreen';
import { useAuth } from '../src/auth/AuthContext';

jest.mock('../src/auth/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = require('react-native');
  return { SafeAreaView: View };
});

test('muestra la única disciplina del club para una cuenta antigua', async () => {
  const updateProfile = jest.fn().mockResolvedValue({});
  useAuth.mockReturnValue({
    user: { username: 'ana', role: 'ATHLETE', club: { name: 'Club', disciplines: ['Boxeo'] } },
    updateProfile, logout: jest.fn(),
  });
  const screen = await render(<ProfileScreen />);
  expect(screen.getByText('Boxeo')).toBeTruthy();
  expect(screen.queryByText('Disciplina del club')).toBeNull();
  await fireEvent.press(screen.getByText('Guardar cambios'));
  await waitFor(() => expect(updateProfile).toHaveBeenCalledWith(expect.objectContaining({ discipline: 'Boxeo' })));
});

test('permite guardar una disciplina elegida de las del club', async () => {
  const updateProfile = jest.fn().mockResolvedValue({});
  useAuth.mockReturnValue({
    user: { username: 'luis', role: 'TRAINER', club: { name: 'Club', disciplines: ['Boxeo', 'MMA'] } },
    updateProfile, logout: jest.fn(),
  });
  const screen = await render(<ProfileScreen />);
  await fireEvent.press(screen.getByText('MMA'));
  await fireEvent.press(screen.getByText('Guardar cambios'));
  await waitFor(() => expect(updateProfile).toHaveBeenCalledWith(expect.objectContaining({ discipline: 'MMA' })));
});
