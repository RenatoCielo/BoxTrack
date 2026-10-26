export const MAX_PER_PRODUCT = 20;

// Un carrito es un mapa { [productId]: cantidad }. Los precios y el stock siempre vienen del servidor.
export function addItem(cart, product, quantity = 1) {
  const current = cart[product.id] || 0;
  const limit = Math.min(MAX_PER_PRODUCT, product.stock);
  const next = Math.min(current + quantity, limit);
  if (next <= 0) return cart;
  return { ...cart, [product.id]: next };
}

export function setQuantity(cart, productId, quantity) {
  if (quantity <= 0) {
    const { [productId]: _removed, ...rest } = cart;
    return rest;
  }
  return { ...cart, [productId]: Math.min(quantity, MAX_PER_PRODUCT) };
}

// Cruza el carrito guardado con los productos vigentes: descarta lo que ya no existe y ajusta al stock.
export function reconcile(cart, products) {
  const byId = new Map(products.map((p) => [String(p.id), p]));
  const next = {};
  Object.entries(cart).forEach(([id, quantity]) => {
    const product = byId.get(String(id));
    if (!product || !product.is_active || product.stock < 1) return;
    next[id] = Math.min(quantity, product.stock, MAX_PER_PRODUCT);
  });
  return next;
}

export function cartLines(cart, products) {
  const byId = new Map(products.map((p) => [String(p.id), p]));
  return Object.entries(cart)
    .map(([id, quantity]) => ({ product: byId.get(String(id)), quantity }))
    .filter((line) => line.product)
    .map((line) => ({ ...line, subtotal: Number(line.product.price) * line.quantity }));
}

export const cartTotal = (lines) => lines.reduce((sum, line) => sum + line.subtotal, 0);
export const cartCount = (cart) => Object.values(cart).reduce((sum, q) => sum + q, 0);

export function toOrderItems(cart) {
  return Object.entries(cart).map(([product, quantity]) => ({ product: Number(product), quantity }));
}
