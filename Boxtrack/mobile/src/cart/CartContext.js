import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../auth/AuthContext';
import { addItem, cartCount, reconcile, setQuantity } from './cartLogic';

const CartContext = createContext(null);
const keyFor = (user) => `boxtrack.cart.${user.id}`;

// El carrito se guarda por usuario en el dispositivo; no contiene precios ni datos sensibles.
export function CartProvider({ children }) {
  const { user } = useAuth();
  const [cart, setCart] = useState({});
  const loaded = useRef(false);

  useEffect(() => {
    loaded.current = false;
    setCart({});
    if (!user) return;
    AsyncStorage.getItem(keyFor(user))
      .then((raw) => setCart(raw ? JSON.parse(raw) : {}))
      .catch(() => setCart({}))
      .finally(() => { loaded.current = true; });
  }, [user?.id]);

  useEffect(() => {
    if (user && loaded.current) AsyncStorage.setItem(keyFor(user), JSON.stringify(cart)).catch(() => {});
  }, [cart, user?.id]);

  const add = useCallback((product, quantity) => setCart((prev) => addItem(prev, product, quantity)), []);
  const setQty = useCallback((id, quantity) => setCart((prev) => setQuantity(prev, id, quantity)), []);
  const clear = useCallback(() => setCart({}), []);
  const sync = useCallback((products) => setCart((prev) => {
    const next = reconcile(prev, products);
    return JSON.stringify(next) === JSON.stringify(prev) ? prev : next;
  }), []);

  const value = useMemo(() => ({ cart, count: cartCount(cart), add, setQty, clear, sync }), [cart, add, setQty, clear, sync]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart debe usarse dentro de CartProvider');
  return ctx;
}
