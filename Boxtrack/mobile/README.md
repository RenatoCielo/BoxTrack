# BoxTrack Mobile

Aplicación móvil nativa (Expo SDK 58 + React Native) que consume la misma API Django REST de la web. Comparte usuarios, roles, permisos y aislamiento por club; no tiene base de datos ni lógica de negocio propia (el backend siempre decide).

## Requisitos
- Node.js 20+ y npm
- Backend BoxTrack en ejecución
- App **Expo Go** (dispositivo físico) o Android Studio / Xcode (emulador)

## Instalación y ejecución
```bash
cd mobile
npm install
npx expo start
```
Escanea el QR con Expo Go, o pulsa `a` (Android) / `i` (iOS) para un emulador.

## Conexión con la API
La URL se resuelve en `src/config.js` en este orden:
1. `EXPO_PUBLIC_API_URL` (ej. `EXPO_PUBLIC_API_URL=https://api.miclub.cl/api`).
2. La IP LAN del equipo que sirve Metro (la detecta Expo) + puerto 8000.
3. `10.0.2.2` en el emulador Android.
4. `localhost` (solo simulador iOS / web).

`localhost` **no** sirve en un teléfono físico. Para pruebas locales:
```bash
# backend: escuchar en toda la red y permitir la IP del PC
set ALLOWED_HOSTS=192.168.1.50,10.0.2.2,localhost,127.0.0.1
python manage.py runserver 0.0.0.0:8000
```
El teléfono y el PC deben estar en la misma red Wi‑Fi. No hay credenciales en el código: usa variables de entorno `EXPO_PUBLIC_*` (archivos `.env*.local` están ignorados por Git).

## Funciones por rol
| Módulo | Admin | Entrenador | Deportista |
|---|---|---|---|
| Login / sesión segura (SecureStore), perfil, contraseña | ✔ | ✔ | ✔ |
| Club y disciplinas, notificaciones | ✔ | ✔ | ✔ |
| Clases, cupos | ✔ | ✔ (nómina) | ✔ |
| Reservas / cancelaciones (regla de membresía obligatoria por club) | ✔ | ✔ | ✔ |
| Membresías: planes, solicitud, historial | ✔ | — | ✔ |
| Membresías: confirmar/rechazar, interruptor de membresía obligatoria | ✔ | — | — |
| Combates entre clubes: consulta | ✔ | ✔ | ✔ (solo lectura) |
| Combates: proponer, aceptar, rechazar, cancelar, resultados; solicitudes de competidor | ✔ | ✔ (sin revisar solicitudes) | — |
| Tienda, carrito (persistido por usuario), pedidos, comprobante de transferencia | ✔ | ✔ | ✔ |
| Pedidos: aprobar comprobante, preparar/entregar | ✔ | — | — |

## Pagos
- **Membresías con Mercado Pago:** el deportista elige el método de pago en el plan. Si `GET /memberships/settings/` informa que Mercado Pago está disponible, la app crea la compra con `POST /memberships/payments/`, abre el `checkout_url` en el navegador del sistema y, al volver (o con "Actualizar estado"), consulta el estado real. La membresía se activa solo cuando el webhook del backend confirma el pago; volver del checkout no aprueba nada. Si ningún proveedor está configurado, se explica en el selector y quedan los métodos manuales. Para cambiar el método de una solicitud pendiente, primero hay que cancelarla.
- **Renovaciones:** la app consulta `GET /memberships/renewal/` y permite renovar dentro de los 7 días previos al vencimiento o después de vencer. La renovación anticipada empieza al día siguiente del fin ya pagado; la vencida empieza al confirmarse. Un pago pendiente no activa el nuevo período y la app conserva el historial.
- **Transferencia bancaria:** se muestran los datos configurados por el administrador en la tienda del mismo club. El deportista adjunta una imagen del comprobante y el administrador la abre y la aprueba o rechaza desde Membresías. Si se rechaza, puede enviar otra; las anteriores se conservan. La membresía o renovación solo se confirma al aprobar el comprobante.
- La tienda usa Mercado Pago **solo si el backend tiene credenciales** (`/store/checkout-config/`), con el mismo criterio.
- Para probar pagos reales necesitas en el `.env` de la raíz: `MERCADOPAGO_ACCESS_TOKEN` (de prueba), `MERCADOPAGO_WEBHOOK_SECRET`, `MERCADOPAGO_NOTIFICATION_URL` (URL HTTPS pública hacia `/api/store/payments/mercadopago/webhook/`, p. ej. un túnel) y `FRONTEND_URL`. Estado: **no validado contra Mercado Pago real ni en dispositivo nativo**.

## Pruebas
```bash
npm test                              # Jest: cliente API, reglas, carrito, combates
npx expo export --platform android    # verifica que el bundle compila
```
