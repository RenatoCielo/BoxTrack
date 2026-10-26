import { addItem, cartCount, cartLines, cartTotal, reconcile, setQuantity, toOrderItems } from '../src/cart/cartLogic';

const products = [
  { id: 1, name: 'Guantes', price: '25000.00', stock: 3, is_active: true },
  { id: 2, name: 'Vendas', price: '5000.00', stock: 0, is_active: true },
  { id: 3, name: 'Casco', price: '40000.00', stock: 50, is_active: true }
];

describe('cartLogic', () => {
  test('addItem respeta el stock y el máximo por producto', () => {
    let cart = addItem({}, products[0], 2);
    cart = addItem(cart, products[0], 5);
    expect(cart[1]).toBe(3);
    expect(addItem({}, products[2], 99)[3]).toBe(20);
  });

  test('no agrega productos sin stock', () => {
    expect(addItem({}, products[1], 1)).toEqual({});
  });

  test('setQuantity elimina con cantidad cero', () => {
    expect(setQuantity({ 1: 2, 3: 1 }, 1, 0)).toEqual({ 3: 1 });
  });

  test('reconcile descarta productos inexistentes o agotados y ajusta cantidades', () => {
    expect(reconcile({ 1: 10, 2: 1, 9: 1 }, products)).toEqual({ 1: 3 });
  });

  test('totales y payload del pedido (sin precios)', () => {
    const cart = { 1: 2, 3: 1 };
    const lines = cartLines(cart, products);
    expect(cartTotal(lines)).toBe(90000);
    expect(cartCount(cart)).toBe(3);
    expect(toOrderItems(cart)).toEqual([{ product: 1, quantity: 2 }, { product: 3, quantity: 1 }]);
  });
});
