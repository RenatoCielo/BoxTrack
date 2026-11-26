import { useEffect, useMemo, useState } from 'react';
import { Check, Download, FileCheck2, Minus, Package, Pencil, Plus, ShoppingBag, ShoppingCart, Trash2, Upload, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const categories = [
  ['GLOVES', 'Guantes'], ['WRAPS', 'Vendas'], ['HEADGEAR', 'Cabezal'], ['MOUTHGUARD', 'Bucal'],
  ['BOOTS', 'Botas'], ['CLOTHING', 'Vestimenta'], ['PROTECTIVE', 'Protección'], ['SUPPLEMENTS', 'Complementos'], ['OTHER', 'Otros']
];
const categoryMarks = {
  GLOVES: 'GLV', WRAPS: 'WRP', HEADGEAR: 'HDG', MOUTHGUARD: 'MTH',
  BOOTS: 'BTS', CLOTHING: 'CLB', PROTECTIVE: 'PRT', SUPPLEMENTS: 'SPT', OTHER: 'GEAR',
};
const orderStatus = { PENDING: 'Pendiente', PAID: 'Pagado', READY: 'Listo para retirar', COMPLETED: 'Retirado', CANCELLED: 'Cancelado' };
const priceFormat = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

function ProductArtwork({ product, isAdmin, onEdit }) {
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => setImageFailed(false), [product.image_url]);
  return <div className="product-image">
    {product.image_url && !imageFailed
      ? <img src={product.image_url} alt={product.name} loading="lazy" onError={() => setImageFailed(true)} />
      : <div className={`product-placeholder product-placeholder-${product.category.toLowerCase()}`} role="img" aria-label={`Imagen ilustrativa de ${product.name}`}>
        <span className="product-placeholder-brand">BOXTRACK <i>FIGHT GEAR</i></span>
        <span className="product-placeholder-mark"><Package size={30} /><b>{categoryMarks[product.category] || 'GEAR'}</b></span>
        <strong>{product.name}</strong>
        <small>{categories.find(([key]) => key === product.category)?.[1] || 'Equipamiento'}</small>
      </div>}
    {isAdmin && <button className="product-edit" onClick={onEdit} aria-label={`Editar ${product.name}`}><Pencil size={15} /></button>}
  </div>;
}

function ProductDialog({ product, onClose, onSave, busy, error }) {
  const [values, setValues] = useState({ name: '', description: '', category: 'GLOVES', sku: '', price: '', stock: 0, image_url: '', is_active: true, ...product });
  const [imageFailed, setImageFailed] = useState(false);
  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  return <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="product-form-title">
    <header className="dialog-heading"><div><p className="eyebrow">INVENTARIO DEL CLUB</p><h2 id="product-form-title">{product?.id ? 'Editar producto' : 'Agregar producto'}</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
    <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSave(values); }}><div className="field-grid">
      <label className="field-label"><span>Nombre *</span><input className="control" name="name" required value={values.name} onChange={update} /></label>
      <label className="field-label"><span>Categoría</span><select className="control" name="category" value={values.category} onChange={update}>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="field-label"><span>Precio (CLP) *</span><input className="control" type="number" min="1" step="1" name="price" required value={values.price} onChange={update} /></label>
      <label className="field-label"><span>Stock *</span><input className="control" type="number" min="0" step="1" name="stock" required value={values.stock} onChange={update} /></label>
      <label className="field-label"><span>SKU</span><input className="control" name="sku" value={values.sku} onChange={update} /></label>
      <label className="field-label"><span>URL de imagen</span><input className="control" type="text" name="image_url" value={values.image_url} onChange={(event) => { setImageFailed(false); update(event); }} placeholder="https://... o /product-artwork.svg" /><small>Usa un enlace público directo o el logo de tienda incluido.</small></label>
      {values.image_url && <div className="product-form-image-preview">{imageFailed ? <span>No se pudo cargar esta imagen. Comprueba que el enlace sea público y directo.</span> : <img src={values.image_url} alt={`Vista previa de ${values.name || 'producto'}`} onError={() => setImageFailed(true)} />}</div>}
      <label className="field-label field-wide"><span>Descripción</span><textarea className="control" name="description" rows="3" value={values.description} onChange={update} /></label>
      <label className="checkbox-control"><input type="checkbox" checked={Boolean(values.is_active)} onChange={(event) => setValues({ ...values, is_active: event.target.checked })} /><span>Disponible para venta</span></label>
    </div>{error && <div className="notice notice-error">{error}</div>}<footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy}>{busy ? 'Guardando...' : 'Guardar producto'}</button></footer></form>
  </section></div>;
}

function TransferInstructionsDialog({ value, onClose, onSave, busy, error }) {
  const [instructions, setInstructions] = useState(value);
  return <div className="modal-scrim"><section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="transfer-settings-title">
    <header className="dialog-heading"><div><p className="eyebrow">PAGO POR TRANSFERENCIA</p><h2 id="transfer-settings-title">Datos bancarios del gimnasio</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
    <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSave(instructions); }}><label className="field-label"><span>Instrucciones para el comprador</span><textarea className="control" rows="6" maxLength="2000" required value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder={'Banco\nTipo y número de cuenta\nTitular y RUT\nCorreo para enviar comprobante'} /></label>{error && <div className="notice notice-error">{error}</div>}<footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy}>{busy ? 'Guardando...' : 'Guardar datos'}</button></footer></form>
  </section></div>;
}

function WebpaySimulation({ order, result, busy, error, onDecision, onClose }) {
  const [card, setCard] = useState({ number: '', holder: '', expiry: '', cvv: '' });
  const total = priceFormat.format(order.total);

  const handleSubmit = (event) => {
    event.preventDefault();
    onDecision(event.nativeEvent.submitter.value);
  };

  const updateCard = (event) => {
    const { name, value } = event.target;
    if (name === 'number') {
      setCard((current) => ({ ...current, number: value.replace(/\D/g, '').slice(0, 19) }));
    } else if (name === 'expiry') {
      const digits = value.replace(/\D/g, '').slice(0, 4);
      setCard((current) => ({ ...current, expiry: digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits }));
    } else if (name === 'cvv') {
      setCard((current) => ({ ...current, cvv: value.replace(/\D/g, '').slice(0, 4) }));
    } else {
      setCard((current) => ({ ...current, [name]: value }));
    }
  };

  return <section className="page-stack webpay-page">
    <header className="page-heading"><div><p className="eyebrow">ENTORNO DE PRUEBA</p><h1>Pago con Webpay</h1><p className="page-description">Simulación segura: no se realizará ningún cobro real.</p></div>{!result && <button className="button button-secondary" onClick={onClose}>Volver a mis pedidos</button>}</header>
    <div className="webpay-window surface-panel">
      <header className="webpay-header"><span className="webpay-logo">webpay <b>plus</b></span><span>Transacción segura · Simulación</span></header>
      {result ? <div className={`webpay-result ${result.status === 'PAID' ? 'is-approved' : 'is-rejected'}`}>
        <div className="webpay-result-icon">{result.status === 'PAID' ? <Check size={30} /> : <X size={30} />}</div>
        <p className="eyebrow">RESULTADO DE LA TRANSACCIÓN</p>
        <h2>{result.status === 'PAID' ? 'Pago aprobado' : 'Pago rechazado'}</h2>
        <p>{result.status === 'PAID' ? 'Tu pago de prueba fue aprobado. El pedido quedó registrado como pagado.' : 'La respuesta de prueba fue rechazada. No se realizó ningún cobro y el stock quedó liberado.'}</p>
        <dl><div><dt>Pedido</dt><dd>#{result.id}</dd></div><div><dt>Monto</dt><dd>{priceFormat.format(result.total)}</dd></div><div><dt>Referencia</dt><dd>{result.payment_reference}</dd></div></dl>
        <button className="button primary-btn" onClick={onClose}>Volver a mis pedidos</button>
      </div> : <div className="webpay-content">
        <form className="webpay-form" onSubmit={handleSubmit}>
          <div className="webpay-form-heading"><div><p className="eyebrow">DATOS DE PAGO DE PRUEBA</p><h2>Tarjeta de crédito o débito</h2></div><span className="webpay-card-mark">VISA</span></div>
          <label className="field-label"><span>Número de tarjeta</span><input className="control" name="number" inputMode="numeric" autoComplete="off" placeholder="1234 5678 9012 3456" value={card.number} onChange={updateCard} required minLength="13" maxLength="19" pattern="[0-9]{13,19}" title="Ingresa entre 13 y 19 dígitos, sin espacios." /></label>
          <label className="field-label"><span>Nombre del titular</span><input className="control" name="holder" autoComplete="off" placeholder="Nombre como aparece en la tarjeta" value={card.holder} onChange={updateCard} required /></label>
          <div className="webpay-card-fields">
            <label className="field-label"><span>Vencimiento</span><input className="control" name="expiry" inputMode="numeric" autoComplete="off" placeholder="MM/AA" value={card.expiry} onChange={updateCard} required pattern="(0[1-9]|1[0-2])/[0-9]{2}" title="Usa el formato MM/AA." /></label>
            <label className="field-label"><span>CVV</span><input className="control" name="cvv" inputMode="numeric" autoComplete="off" placeholder="123" value={card.cvv} onChange={updateCard} required minLength="3" maxLength="4" pattern="[0-9]{3,4}" title="Ingresa 3 o 4 dígitos." /></label>
          </div>
          {error && <div className="notice notice-error">{error}</div>}
          <div className="webpay-decisions"><button className="button primary-btn" name="decision" value="APPROVE" disabled={busy}>{busy ? 'Enviando respuesta...' : 'Aprobar pago de prueba'}</button><button className="button button-secondary" name="decision" value="REJECT" disabled={busy}>Rechazar pago de prueba</button></div>
          <p className="webpay-privacy-note">La tarjeta se valida solo en este formulario. Sus datos no se envían ni se guardan.</p>
        </form>
        <aside className="webpay-summary"><p className="eyebrow">RESUMEN DE COMPRA</p><h2>Pedido #{order.id}</h2><p>Equipamiento de tu tienda BoxTrack</p><div><span>Total a pagar</span><strong>{total}</strong></div><small>Al ser una simulación, puedes elegir el resultado de la respuesta del pago.</small></aside>
      </div>}
    </div>
  </section>;
}

export function StorePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [onlinePaymentAvailable, setOnlinePaymentAvailable] = useState(false);
  const [webpaySimulationAvailable, setWebpaySimulationAvailable] = useState(false);
  const [bankTransferInstructions, setBankTransferInstructions] = useState('');
  const [cart, setCart] = useState(() => {
    try { return JSON.parse(localStorage.getItem('boxtrack.cart') || '[]'); } catch { return []; }
  });
  const [category, setCategory] = useState('ALL');
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState('catalog');
  const [productEditor, setProductEditor] = useState(null);
  const [transferEditorOpen, setTransferEditorOpen] = useState(false);
  const [proofFiles, setProofFiles] = useState({});
  const [busyProofOrder, setBusyProofOrder] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('RESERVE');
  const [webpayOrder, setWebpayOrder] = useState(null);
  const [webpayResult, setWebpayResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    setError('');
    try {
      const [productRows, orderRows, checkoutConfig] = await Promise.all([
        readCollection('/store/products/'),
        readCollection('/store/orders/'),
        api.get('/store/checkout-config/').then((response) => response.data)
      ]);
      setProducts(productRows);
      setOrders(orderRows);
      setOnlinePaymentAvailable(checkoutConfig.mercado_pago_available);
      setWebpaySimulationAvailable(checkoutConfig.webpay_simulation_available);
      setBankTransferInstructions(checkoutConfig.bank_transfer_instructions || '');
      if (!checkoutConfig.mercado_pago_available && paymentMethod === 'MERCADO_PAGO') setPaymentMethod('RESERVE');
      if (!checkoutConfig.webpay_simulation_available && paymentMethod === 'WEBPAY') setPaymentMethod('RESERVE');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { localStorage.setItem('boxtrack.cart', JSON.stringify(cart)); }, [cart]);

  const visibleProducts = useMemo(() => products.filter((product) =>
    (category === 'ALL' || product.category === category) &&
    `${product.name} ${product.description} ${product.sku}`.toLowerCase().includes(query.toLowerCase())
  ), [products, category, query]);
  const cartCount = cart.reduce((count, item) => count + item.quantity, 0);
  const cartTotal = cart.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0);

  const saveProduct = async (values) => {
    setBusy(true);
    setError('');
    const payload = { ...values, stock: Number(values.stock), price: Number(values.price) };
    try {
      if (productEditor?.id) await api.patch(`/store/products/${productEditor.id}/`, payload);
      else await api.post('/store/products/', payload);
      setProductEditor(null);
      await load();
      setNotice('Inventario actualizado.');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const saveTransferInstructions = async (instructions) => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.patch('/store/checkout-config/', { bank_transfer_instructions: instructions });
      setBankTransferInstructions(data.bank_transfer_instructions);
      setTransferEditorOpen(false);
      setNotice('Datos de transferencia actualizados.');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const addToCart = (product) => {
    setCart((current) => {
      const existing = current.find((item) => item.id === product.id);
      if (existing) return current.map((item) => item.id === product.id ? { ...item, quantity: Math.min(item.quantity + 1, product.stock) } : item);
      return [...current, { id: product.id, name: product.name, price: product.price, stock: product.stock, quantity: 1 }];
    });
  };

  const changeQuantity = (productId, delta) => setCart((current) => current.flatMap((item) => {
    if (item.id !== productId) return [item];
    const quantity = item.quantity + delta;
    return quantity <= 0 ? [] : [{ ...item, quantity: Math.min(quantity, item.stock) }];
  }));

  const checkout = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/store/orders/', {
        payment_method: paymentMethod,
        items: cart.map((item) => ({ product: item.id, quantity: item.quantity }))
      });
      setCart([]);
      await load();
      if (paymentMethod === 'WEBPAY') {
        setWebpayOrder(data);
        setWebpayResult(null);
        return;
      }
      setTab('orders');
      if (data.checkout_url) window.location.assign(data.checkout_url);
      else if (paymentMethod === 'RESERVE') setNotice('Productos reservados para retiro en el gimnasio.');
      else setNotice('Pedido registrado. El gimnasio confirmará la transferencia antes del retiro.');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const respondToWebpaySimulation = async (decision) => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post(`/store/orders/${webpayOrder.id}/webpay-simulation/`, { decision });
      setWebpayResult(data);
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const updateOrder = async (order, nextStatus) => {
    try {
      await api.patch(`/store/orders/${order.id}/`, { status: nextStatus });
      await load();
      setNotice(`Pedido #${order.id}: ${orderStatus[nextStatus].toLowerCase()}.`);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const uploadProof = async (order) => {
    const proof = proofFiles[order.id];
    if (!proof) {
      setError('Selecciona primero la imagen o PDF del comprobante.');
      return;
    }
    setBusyProofOrder(order.id);
    setError('');
    const formData = new FormData();
    formData.append('proof', proof);
    try {
      await api.post(`/store/orders/${order.id}/proof/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setProofFiles((current) => ({ ...current, [order.id]: null }));
      await load();
      setNotice('Comprobante enviado. Tu solicitud está en revisión; te avisaremos cuando el gimnasio responda.');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusyProofOrder(null); }
  };

  const downloadProof = async (order) => {
    try {
      const { data } = await api.get(`/store/orders/${order.id}/proof/file/`, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      link.href = url;
      link.download = order.payment_proof_file_name || `comprobante-pedido-${order.id}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const reviewProof = async (order, decision) => {
    let note = '';
    if (decision === 'REJECT') {
      note = window.prompt('Indica brevemente por qué se rechaza el comprobante:') || '';
      if (!note.trim()) return;
    }
    setBusyProofOrder(order.id);
    setError('');
    try {
      await api.post(`/store/orders/${order.id}/proof/review/`, { decision, note });
      await load();
      setNotice(decision === 'APPROVE' ? `Pago del pedido #${order.id} aprobado. Se notificó al deportista.` : `Comprobante del pedido #${order.id} rechazado. Se notificó al deportista.`);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusyProofOrder(null); }
  };

  const visibleOrders = tab === 'proofs'
    ? orders.filter((order) => order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'SUBMITTED')
    : orders;
  const pendingProofCount = orders.filter((order) => order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'SUBMITTED').length;

  if (webpayOrder) {
    return <WebpaySimulation
      order={webpayOrder}
      result={webpayResult}
      busy={busy}
      error={error}
      onDecision={respondToWebpaySimulation}
      onClose={() => {
        setWebpayOrder(null);
        setWebpayResult(null);
        setError('');
        setTab('orders');
      }}
    />;
  }

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">EQUIPAMIENTO Y COMPLEMENTOS</p><h1>Tienda del gimnasio</h1><p className="page-description">Productos, stock y pedidos de tu club.</p></div>{isAdmin && <div className="heading-actions"><button className="button button-secondary" onClick={() => setTransferEditorOpen(true)}>Datos de transferencia</button><button className="button primary-btn" onClick={() => setProductEditor({})}><Plus size={16} /> Agregar producto</button></div>}</header>
    <div className="store-tabs"><button className={tab === 'catalog' ? 'active' : ''} onClick={() => setTab('catalog')}><ShoppingBag size={16} /> Catálogo</button><button className={tab === 'cart' ? 'active' : ''} onClick={() => setTab('cart')}><ShoppingCart size={16} /> Carrito <span>{cartCount}</span></button><button className={tab === 'orders' ? 'active' : ''} onClick={() => setTab('orders')}><Package size={16} /> Pedidos</button>{isAdmin && <button className={tab === 'proofs' ? 'active' : ''} onClick={() => setTab('proofs')}><FileCheck2 size={16} /> Comprobantes <span>{pendingProofCount}</span></button>}</div>
    {notice && <div className="notice notice-success">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}

    {tab === 'catalog' && <>
      <div className="store-filters"><label className="search-field"><span className="sr-only">Buscar productos</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar equipamiento..." /></label><nav className="category-tabs" aria-label="Categorías de productos"><button className={category === 'ALL' ? 'active' : ''} onClick={() => setCategory('ALL')}>Todos</button>{categories.map(([value, label]) => <button key={value} className={category === value ? 'active' : ''} onClick={() => setCategory(value)}>{label}</button>)}</nav></div>
      <div className="store-grid">{visibleProducts.map((product) => <article className="product-card" key={product.id}>
        <ProductArtwork product={product} isAdmin={isAdmin} onEdit={() => setProductEditor(product)} />
        <div className="product-copy"><span className="product-category">{categories.find(([key]) => key === product.category)?.[1] || product.category}</span><h2>{product.name}</h2><p>{product.description || 'Equipamiento disponible en el gimnasio.'}</p><div className="product-buy"><strong>{priceFormat.format(product.price)}</strong><span>{product.stock > 0 ? `${product.stock} disponibles` : 'Agotado'}</span></div><button className="button primary-btn product-add" disabled={product.stock < 1} onClick={() => addToCart(product)}><Plus size={15} /> Añadir al carrito</button></div>
      </article>)}{!visibleProducts.length && <div className="surface-panel empty-state">No encontramos productos con esos filtros.</div>}</div>
    </>}

    {tab === 'cart' && <div className="checkout-layout"><section className="cart-lines surface-panel"><div className="section-heading"><div><p className="eyebrow">TU SELECCIÓN</p><h2>Carrito</h2></div></div>{cart.length ? cart.map((item) => <div className="cart-line" key={item.id}><div className="cart-product-mark"><Package size={18} /></div><div className="cart-product-name"><strong>{item.name}</strong><span>{priceFormat.format(item.price)} c/u</span></div><div className="quantity-stepper"><button onClick={() => changeQuantity(item.id, -1)} aria-label="Quitar una unidad"><Minus size={14} /></button><span>{item.quantity}</span><button onClick={() => changeQuantity(item.id, 1)} disabled={item.quantity >= item.stock} aria-label="Agregar una unidad"><Plus size={14} /></button></div><strong className="cart-subtotal">{priceFormat.format(Number(item.price) * item.quantity)}</strong><button className="icon-button delete-action" onClick={() => setCart((current) => current.filter((product) => product.id !== item.id))} aria-label={`Quitar ${item.name}`}><Trash2 size={16} /></button></div>) : <div className="empty-state">Tu carrito está vacío. Agrega productos del catálogo.</div>}</section>
      <aside className="checkout-panel surface-panel"><p className="eyebrow">RESERVA Y PAGO</p><h2>Resumen del pedido</h2><label className="field-label"><span>Elige cómo continuar</span><select className="control" value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}><option value="RESERVE">Reservar para retirar y pagar en el gimnasio</option><option value="BANK_TRANSFER" disabled={!bankTransferInstructions.trim()}>Transferencia bancaria{bankTransferInstructions.trim() ? '' : ' (no configurada)'}</option><option value="MERCADO_PAGO" disabled={!onlinePaymentAvailable}>Mercado Pago: débito o crédito{onlinePaymentAvailable ? '' : ' (no configurado)'}</option><option value="WEBPAY" disabled={!webpaySimulationAvailable}>Webpay (simulación){webpaySimulationAvailable ? '' : ' (solo disponible en desarrollo)'}</option></select></label>{paymentMethod === 'BANK_TRANSFER' && <div className="bank-transfer-details"><strong>Datos para transferir</strong><p>{bankTransferInstructions}</p><small>El pedido queda reservado hasta que el gimnasio verifique la transferencia.</small></div>}{paymentMethod === 'RESERVE' && <p className="checkout-note payment-setup-note">Apartaremos el stock para que retires y pagues en el gimnasio.</p>}{paymentMethod === 'WEBPAY' && <p className="checkout-note">Simulación de Webpay: ingresa datos de prueba y selecciona si la respuesta del pago se aprueba o rechaza. No se realiza un cobro real.</p>}{!onlinePaymentAvailable && <p className="checkout-note">Mercado Pago requiere configuración del proveedor en el servidor.</p>}<div className="checkout-total"><span>Total</span><strong>{priceFormat.format(cartTotal)}</strong></div><button className="button primary-btn checkout-button" disabled={!cart.length || busy} onClick={checkout}>{busy ? 'Procesando...' : paymentMethod === 'MERCADO_PAGO' ? 'Pagar con Mercado Pago' : paymentMethod === 'WEBPAY' ? 'Continuar a Webpay' : paymentMethod === 'BANK_TRANSFER' ? 'Confirmar transferencia' : 'Reservar productos'}</button><p className="checkout-note">Pedidos con retiro en el gimnasio.</p></aside>
    </div>}

    {(tab === 'orders' || tab === 'proofs') && <div className="order-list">{visibleOrders.length ? visibleOrders.map((order) => <article className="order-card surface-panel" key={order.id}><header><div><p className="eyebrow">PEDIDO #{order.id} · {new Date(order.created_at).toLocaleDateString('es-CL')}</p><h2>{isAdmin ? order.buyer_name : 'Tu pedido'}</h2></div><span className={`order-status order-${order.status.toLowerCase()}`}>{order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'SUBMITTED' ? 'Comprobante en revisión' : order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'REJECTED' ? 'Comprobante rechazado' : order.status === 'PENDING' && order.payment_method === 'RESERVE' ? 'Reservado para retiro' : orderStatus[order.status]}</span></header><div className="order-items">{order.items.map((item) => <div key={item.id}><span>{item.quantity} × {item.product_name}</span><span>{priceFormat.format(item.subtotal)}</span></div>)}</div><footer><div><small>{order.payment_method === 'MERCADO_PAGO' ? 'Mercado Pago · débito/crédito' : order.payment_method === 'WEBPAY' ? 'Webpay · simulación' : order.payment_method === 'BANK_TRANSFER' ? 'Transferencia bancaria' : 'Reserva para retiro'}</small><strong>{priceFormat.format(order.total)}</strong></div>{isAdmin && order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'SUBMITTED' && <div className="proof-review-actions"><button className="button button-secondary" onClick={() => downloadProof(order)}><Download size={15} /> Ver comprobante</button><button className="button button-secondary" disabled={busyProofOrder === order.id} onClick={() => reviewProof(order, 'REJECT')}>Rechazar</button><button className="button primary-btn" disabled={busyProofOrder === order.id} onClick={() => reviewProof(order, 'APPROVE')}><Check size={15} /> Aprobar pago</button></div>}{order.user === user?.id && order.payment_method === 'BANK_TRANSFER' && order.status === 'PENDING' && order.proof_status !== 'SUBMITTED' && <div className="proof-upload-row"><div className="proof-upload-input"><Upload size={15} /><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" aria-label="Seleccionar comprobante de transferencia" onChange={(event) => setProofFiles((current) => ({ ...current, [order.id]: event.target.files?.[0] || null }))} /><span>{proofFiles[order.id]?.name || (order.proof_status === 'REJECTED' ? 'Adjunta otro comprobante' : 'Adjuntar comprobante')}</span></div><button className="button primary-btn" disabled={!proofFiles[order.id] || busyProofOrder === order.id} onClick={() => uploadProof(order)}>{busyProofOrder === order.id ? 'Enviando...' : 'Enviar comprobante'}</button></div>}{order.user === user?.id && order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'SUBMITTED' && <p className="proof-pending-note">Comprobante recibido. Tu solicitud está en revisión; recibirás una notificación al resolverse.</p>}{order.proof_status === 'REJECTED' && order.proof_review_note && <p className="notice notice-error proof-rejection-note">Motivo del rechazo: {order.proof_review_note}</p>}{isAdmin && order.payment_method === 'BANK_TRANSFER' && order.proof_status === 'APPROVED' && <span className="proof-approved-note">Comprobante aprobado</span>}{isAdmin && <select className="control order-status-select" value={order.status} onChange={(event) => updateOrder(order, event.target.value)}>{Object.entries(orderStatus).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}{order.payment_method === 'WEBPAY' && order.status === 'PENDING' && <button className="button primary-btn" onClick={() => { setWebpayOrder(order); setWebpayResult(null); }}>Completar pago de prueba</button>}{order.checkout_url && order.status === 'PENDING' && <a className="button primary-btn" href={order.checkout_url}>Completar pago</a>}</footer></article>) : <div className="surface-panel empty-state">{tab === 'proofs' ? 'No hay comprobantes pendientes de revisión.' : 'Todavía no hay pedidos.'}</div>}</div>}
    {productEditor && <ProductDialog product={productEditor.id ? productEditor : undefined} onClose={() => setProductEditor(null)} onSave={saveProduct} busy={busy} error={error} />}
    {transferEditorOpen && <TransferInstructionsDialog value={bankTransferInstructions} onClose={() => setTransferEditorOpen(false)} onSave={saveTransferInstructions} busy={busy} error={error} />}
  </section>;
}