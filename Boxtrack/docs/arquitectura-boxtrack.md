# Arquitectura de BOXTRACK

## 1. Objetivo
BoxTrack propone una plataforma para clubes y academias de boxeo con foco en la gestión administrativa y el seguimiento deportivo. La solución prioriza indicadores útiles para entrenadores, administradores y deportistas, en vez de una simple administración de gimnasios.

## 2. Arquitectura general

```mermaid
flowchart LR
    A[Usuario] --> B[Frontend React]
    B --> C[API Django REST Framework]
    C --> D[(MySQL)]
    C --> E[Auth JWT]
    C --> F[Servicios de negocio]
    F --> G[Dashboards, alertas, reportes]
```

## 3. Capa frontend

- React + Vite
- Rutas protegidas por rol
- Componentes reutilizables para cards, tables, forms y charts
- Diseño mobile-first con menú lateral en desktop
- Configuración de perfil, apodo visible, privacidad del teléfono y tema claro/oscuro
- Recharts para estadísticas y evolución deportiva
- Lucide para iconografía
- Axios para consumo de API
- Páginas: login, dashboard, deportistas, competidores, entrenadores, clases y cupos, peleas, asistencia, alertas, notificaciones, tienda, membresías, configuración y panel de administración global (solo superusuario)
- Membresías (`MembershipsPage`): el administrador crea y edita planes y confirma o rechaza pagos; el deportista ve los planes de su club, solicita uno y consulta el estado e historial de su membresía
- Carrito de la tienda: se guarda por usuario en el navegador (no se comparte entre cuentas), se sincroniza con el catálogo real al cargar (precio, stock e imagen vigentes; se retiran productos inactivos o agotados), permite vaciarlo con confirmación y muestra la imagen del producto. El total definitivo y el stock siempre los valida el backend al crear el pedido
- La agenda de clases (`TrainingPage`) se refresca sola cada 15 segundos y al volver a la pestaña o ventana, para que los deportistas vean de inmediato las clases nuevas que programa el administrador
- Membresía obligatoria (`MembershipsPage` y `TrainingPage`): el administrador activa o desactiva "Exigir membresía activa para reservar clases" con un selector (Activado/Desactivado) que guarda y persiste por club. Con la opción activa, el botón de reservar queda deshabilitado para quien no tiene membresía vigente y se muestra un mensaje con el enlace "Ver planes disponibles" (`/memberships`); si la membresía está pendiente de pago, el mensaje lo indica. El backend vuelve a validar (409 `MEMBERSHIP_REQUIRED`)
- Competidores y combates (`CompetitionPage`, ruta `/competition`, menú "Combates entre clubes" con icono de apretón de manos; "Historial de combates" conserva el de espadas). El entrenador solicita el paso de un deportista a competidor; el administrador aprueba o rechaza con una nota escrita en la misma pantalla (sin `prompt()` ni `confirm()`, que no funcionan bien en móviles ni en navegadores integrados). Los combates se proponen eligiendo un competidor propio y uno del directorio de otros clubes; el club rival acepta o rechaza, el club proponente solo puede cancelar. El resultado se registra con botones "¿Quién ganó?" (ganador o empate) y la cancelación pide confirmación en línea. El deportista solo consulta
- Avisos: `.notice-success` es verde (claro y oscuro) y `.notice-error` rojo; la regla antigua que pintaba los éxitos de rosado se eliminó
- Validación visual (navegador, 390/768/1280 px): sin desbordamiento horizontal en membresías, clases y combates

### Aplicación móvil (`mobile/`)
- Expo SDK 58 + React Native, independiente del frontend web. Consume la misma API DRF/JWT: no tiene base de datos ni reglas de negocio propias (el backend valida permisos, cupos, membresía obligatoria y aislamiento por club).
- Estructura: `src/api` (cliente con refresh de token, errores y timeout), `src/auth` (sesión en SecureStore), `src/cart` (carrito por usuario, sin precios), `src/screens`, `src/components`, `src/navigation` (pestañas Inicio/Clases/Membresías/Más según rol), `src/utils` (reglas puras probadas).
- Pantallas: inicio, perfil, club, notificaciones, clases y reservas, membresías (deportista y administrador), combates entre clubes, tienda/carrito/pedidos con comprobante de transferencia.
- URL de API: `EXPO_PUBLIC_API_URL` → IP LAN del bundler → `10.0.2.2` (emulador Android) → `localhost`. Para teléfonos físicos el backend debe correr en `0.0.0.0:8000` con `ALLOWED_HOSTS` incluyendo la IP del PC. Instrucciones completas en `mobile/README.md`.
- Pagos: la app nunca marca pagos como aprobados. Si `GET /memberships/settings/` informa `mercado_pago_available`, el plan se compra con `POST /memberships/payments/` y se abre el `checkout_url` con `expo-web-browser`; al volver a la app (o a la pantalla) se consulta el estado real del pago. La membresía se activa solo cuando el backend recibe el webhook verificado. No validado en dispositivo ni con Mercado Pago real.
- Verificación: 39 pruebas Jest, bundle Android compilado y flujos probados en Expo web contra el backend (reserva, membresía obligatoria, combates entre clubes, compra con comprobante y aprobación). No se ha probado en emulador ni dispositivo nativo.

## 4. Capa backend

- Django como framework principal
- DRF para endpoints REST
- JWT para sesión y autenticación
- Modelos por dominio para aislar responsabilidades
- Permisos por club y por rol
- Validaciones en servidor y middlewares de seguridad
- Preferencias de perfil servidas por `GET/PATCH /api/auth/profile/`; el teléfono se oculta en las fichas de otros miembros cuando su dueño desactiva el uso compartido
- Módulos (`backend/apps`): `accounts`, `clubs`, `athletes`, `trainers`, `groups`, `trainings`, `attendance`, `evaluations`, `weight_tracking`, `competitions`, `alerts`, `notifications`, `dashboard`, `reports`, `store` y `common` (permisos compartidos)
- Endpoints de cuentas: `register/`, `login/`, `refresh/`, `me/`, `profile/`, `members/` (alta de cuentas del club por el admin) y `password/` (cambio de contraseña, incluido el obligatorio en el primer ingreso)
- Verificación de clubes: al registrarse, un club queda `PENDING` hasta subir su documento (`/api/clubs/<id>/document/`), pasa a `IN_REVIEW` y un superusuario lo aprueba o rechaza (`/api/clubs/pending/`, `/api/clubs/<id>/review/`). Los estados son `PENDING`, `IN_REVIEW`, `NEEDS_INFO` y `APPROVED`. El documento se guarda en almacenamiento privado
- Mientras el club no está aprobado, el administrador puede crear grupos y clases, pero entrenadores y el resto de módulos quedan restringidos. Excepción: los deportistas de un club activo pueden **consultar** las clases (solo lectura) aunque el club esté pendiente, de modo que ven la agenda que el admin programó
- Tienda: productos, pedidos, comprobantes de pago (subida, descarga y revisión por el admin: `NOT_SUBMITTED`, en revisión, aprobado o rechazado) y webhook de MercadoPago
- Membresías por club (`apps.memberships`, API en `/api/memberships/`):
    - `MembershipPlan` (`planes_membresia`): cada club crea y edita sus propios planes (nombre, precio, moneda, duración en días, beneficios, límite de clases semanales opcional, activo/inactivo). El nombre es único dentro del club.
    - `Membership` (`membresias`): contratación de un deportista. Guarda una instantánea del plan (nombre, precio, duración, límite) para que editar el plan no altere lo ya contratado. Estados: `PENDING`, `ACTIVE`, `EXPIRED`, `REJECTED`, `CANCELLED`. Una restricción en base de datos impide tener más de una membresía `PENDING` o `ACTIVE` por deportista.
    - Flujo: el deportista solicita un plan (`POST /api/memberships/`) y queda `PENDING`; el administrador confirma el pago, rechaza con motivo o cancela (`POST /api/memberships/<id>/review/` con `decision` = `CONFIRM`, `REJECT` o `CANCEL`). Al confirmar se fijan las fechas de inicio y fin y se notifica al deportista. El deportista solo puede cancelar su propia solicitud pendiente.
    - El precio y el club salen siempre del servidor; el cliente solo envía el id del plan. Las membresías vencidas pasan a `EXPIRED` al consultarse, sin depender de tareas programadas.
    - Límite semanal en reservas: si el deportista tiene una membresía `ACTIVE` con `weekly_class_limit`, el servidor rechaza (409) una reserva que supere ese número de clases `RESERVED` en la misma semana (lunes a domingo) de la fecha de la clase. Cancelar una reserva libera el cupo semanal. Sin membresía, con plan sin límite o con membresía vencida, las reservas funcionan como antes, para no romper clubes que aún no usan planes. Aplica tanto a reservas del deportista como a inscripciones hechas por el equipo.
    - Exigir membresía para reservar (por club): `MembershipSettings` (`configuracion_membresias`, un registro por club, `require_active_membership`, desactivado por defecto). `GET/PATCH /api/memberships/settings/` (leer: cualquier rol del club; cambiar: solo ADMIN). Si está activado, el servidor responde 409 con `code: MEMBERSHIP_REQUIRED` a quien reserve sin membresía `ACTIVE` vigente en la fecha de la clase (o con una pendiente de pago/vencida), antes de revisar el límite semanal. El frontend (`TrainingPage`) deshabilita el botón y muestra el enlace "Ver planes disponibles", pero la validación real está en el backend. El interruptor está en la página Membresías del admin. Con la opción apagada nada cambia, y cada club tiene su propio valor.
    - Pago manual: el administrador del club confirma o rechaza la solicitud (`POST /memberships/<id>/review/`). Sigue funcionando igual y es la alternativa cuando el club no tiene Mercado Pago.
    - **Pago online con Mercado Pago (P2)** — `apps/memberships/payments.py`, modelo `MembershipPayment` (`pagos_membresia`: usuario, club, plan, membresía, monto y moneda como instantánea del plan, estado, `provider_payment_id` único, expiración):
        - Reutiliza la integración de la tienda (`apps/store/views.py`): mismas variables de entorno, `post_mercadopago_preference`, `webhook_signature_valid` (HMAC-SHA256 de `x-signature`) y `fetch_mercadopago_payment` (consulta del pago a la API oficial). No hay una segunda integración ni un segundo webhook: `/api/store/payments/mercadopago/webhook/` delega según el `external_reference` (`membership:<id>` → membresías; número → pedido de tienda, sin cambios).
        - Endpoints (solo ADMIN/ATHLETE del club): `POST /memberships/payments/` (solo ATHLETE; `{plan}`), `GET /memberships/payments/` (deportista: los suyos; admin: los del club), `GET /memberships/payments/<id>/` y `DELETE` (el comprador cancela su pago pendiente). `GET /memberships/settings/` añade `mercado_pago_available`. Ningún endpoint permite marcar un pago como aprobado.
        - Flujo: el servidor toma plan, precio, moneda y duración de la base de datos (ignora importes del cliente), crea la membresía `PENDING` y el pago `PENDING` (30 min), genera la preferencia y devuelve `checkout_url` (solo al comprador). Una compra abierta del mismo plan se reutiliza (no hay doble cobro); con otra membresía abierta o una solicitud manual pendiente responde 409. Si Mercado Pago falla, la compra se cancela y no se cobra.
        - Confirmación: el retorno del checkout (`?payment=success`) no aprueba nada. Solo el webhook firmado, cuyo pago se vuelve a consultar a la API de Mercado Pago, cambia el estado. `approved` activa la membresía si monto y moneda coinciden con lo registrado (400 si no). Es idempotente: repetir el webhook no reactiva ni duplica; el `provider_payment_id` es único y un segundo cobro aprobado para la misma compra se registra y avisa al administrador sin aplicarse.
        - Estados del pago: `PENDING`, `APPROVED`, `REJECTED` y `CANCELLED` (la membresía se cancela y el deportista puede reintentar), `EXPIRED` (al vencer el checkout), `REFUNDED` (reembolso o contracargo: cancela la membresía) y `REVIEW` (cobro aprobado que llegó tarde y no pudo activarse porque hay otra membresía abierta: avisa al administrador). Un pago aprobado que llega tras rechazo, cancelación o vencimiento reactiva la membresía si el deportista no tiene otra abierta.
        - Cambios del plan: desactivarlo o cambiar su precio después de iniciar la compra no altera lo ya registrado; la membresía conserva la instantánea de precio y condiciones.
        - Preparado para renovaciones (P3): cada pago referencia su membresía y plan y los registros anteriores se conservan; aún no hay renovación ni cobros recurrentes.
        - Configuración necesaria: `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `MERCADOPAGO_NOTIFICATION_URL` (URL pública del webhook) y `FRONTEND_URL` para las `back_urls`. Sin ellas `mercado_pago_available` es `false`, las pantallas ocultan el botón y el endpoint responde 503; nunca se simula un cobro.
        - Errores del proveedor: si Mercado Pago no responde, excede el tiempo de espera o devuelve un cuerpo inesperado (no es un objeto JSON), el webhook responde 502 sin modificar ningún pago, membresía ni pedido, para que Mercado Pago reintente.
        - Tipos de notificación: el webhook solo consulta notificaciones de tipo `payment` (o sin tipo). Las de otro tipo, p. ej. `merchant_order` (indicado en el cuerpo `type`/`topic` o en la consulta `type`/`topic`), se responden 200 con `ignored` tras validar la firma, sin consultar al proveedor, sin tratar su id como id de pago y sin cambiar estados; así no hay reintentos inútiles. Una firma inválida sigue dando 401. La aprobación siempre llega por la notificación `payment`. Para evitar ruido, en el panel de Mercado Pago basta suscribir el evento «Pagos».
        - Niveles de prueba: (1) pruebas automatizadas Django/Jest con el proveedor simulado (`mock`), que verifican nuestra lógica pero no la respuesta real de Mercado Pago; (2) pruebas con proveedor simulado en el navegador, con tokens de marcador (la API real rechaza el token y se comprueba el camino de error); (3) validación real con sandbox de Mercado Pago, **aún no realizada**.
        - Requisitos para declarar P2 completamente validada: credenciales de prueba (`TEST-…`), URL HTTPS pública del webhook, compra con un comprador y tarjetas de prueba verificando firma y monto reales, rechazo y pendiente, y una prueba del checkout y del refresco al volver en un dispositivo o emulador Android nativo.
        - Pruebas: `apps/memberships/test_payments.py` (proveedor simulado; no hay llamadas reales). **No se ha validado con credenciales reales ni con el sandbox de Mercado Pago.**

- Competidores y combates entre clubes (`apps.competitions`, `apps/competitions/inter_club.py`, página `/competition`):
    - `CompetitorRequest` (`solicitudes_competidor`): el entrenador (solo de deportistas asignados a él) solicita el paso a competidor (`POST /api/competitions/competitor-requests/`); el ADMIN del mismo club resuelve (`POST .../<id>/review/` con `decision` `APPROVE` o `REJECT` y `review_note`). Al aprobar solo se marca `is_competitor` en el mismo deportista (no se crea otra cuenta, sigue en la lista general con su filtro). Una restricción impide dos solicitudes pendientes del mismo deportista. Se notifica a admins, entrenador y deportista y el historial de solicitudes se conserva.
    - `FightMatch` (`combates_entre_clubes`): un único registro por combate, visible para ambos clubes y ambos competidores. Estados `PROPOSED`, `ACCEPTED`, `DECLINED`, `CANCELLED`, `COMPLETED`. Endpoints: `GET/POST /api/competitions/matches/`, `POST /api/competitions/matches/<id>/<accept|decline|cancel|result>/`, `GET /api/competitions/directory/` (competidores activos de otros clubes aprobados; solo nombre, club, categoría y peso).
    - Reglas: propone el staff del club del retador (el entrenador solo con sus asignados); ambos deben ser competidores activos de clubes distintos y el club rival debe estar aprobado; no se permiten fechas pasadas ni dos combates abiertos del mismo deportista en una fecha. Acepta o rechaza el staff del club rival; cualquiera de los dos clubes registra el resultado una sola vez (desde la fecha del combate) y se crean los registros `Competition` de cada club (resultado e inverso) para actualizar el récord. El deportista ve sus combates pero no puede modificarlos.

## 5. Base de datos

- MySQL 8.0+
- Modelo relacional normalizado
- Relación obligatoria entre usuarios, clubes y roles
- Aislamiento por club para evitar fuga de información
- Índices sobre búsquedas frecuentes y relaciones clave
- Las tablas y columnas de negocio usan nombres físicos en español en SQLite y MySQL; los nombres internos de Django se conservan para no romper autenticación y permisos.

### Tablas de negocio en DB Browser

| Área | Tablas |
| --- | --- |
| Cuentas y clubes | `roles`, `usuarios`, `clubes` |
| Plantel | `deportistas`, `perfiles_entrenadores`, `grupos` |
| Clases y seguimiento | `clases`, `reservas_clases`, `asistencias`, `evaluaciones`, `registros_peso`, `competencias`, `alertas`, `notificaciones` |
| Tienda | `configuracion_tienda`, `productos`, `pedidos`, `detalle_pedidos` |
| Membresías | `planes_membresia`, `membresias`, `pagos_membresia` |

Las columnas también se guardan en español, por ejemplo `usuarios.nombre_usuario`, `deportistas.fecha_nacimiento`, `clases.fecha_programada` y `pedidos.estado`. En las relaciones, `id_club`, `id_deportista` e `id_usuario` identifican claves foráneas. `id` se mantiene como identificador primario.

Las tablas de infraestructura como `django_migrations`, `django_content_type`, las tablas de sesiones/permisos y las tablas intermedias de permisos de usuario conservan sus nombres estándar de Django. No deben renombrarse ni editarse directamente. Para que el esquema quede actualizado, ejecutar `python manage.py migrate` antes de abrir o volver a cargar `backend/db.sqlite3` en DB Browser.

## 6. Modelos esperados

### Entidades principales
- Club
- Usuario
- Perfil de usuario
- Rol
- Permiso
- Deportista
- Perfil de competidor, con grupo de preparación diferenciado y récord derivado del historial de combates
- Entrenador
- Grupo
- Entrenamiento / clase programada, con capacidad máxima
- Reserva de cupo del deportista en una clase
- Asistencia
- Evaluación deportiva
- Registro de peso
- Competencia
- Resultado de combate
- Alerta
- Notificación
- Objetivo deportivo

## 7. Seguridad

- JWT con tokens de acceso y refresh
- Control de acceso por roles: administrador, entrenador, deportista
- Matriz de permisos:
    - Administrador: crea cuentas, administra perfiles y grupos, programa clases y gestiona la configuración del club.
    - Entrenador: consulta deportistas y grupos; programa clases, registra asistencia y mantiene el seguimiento deportivo y alertas. No administra cuentas ni perfiles del equipo.
    - Deportista: consulta clases, reserva o cancela sus propios cupos y consulta sus notificaciones.
- Los permisos se validan en la API; ocultar una opción en el frontend no sustituye la autorización del backend.
- Validación que un club no acceda a otra base de datos
- Protección de rutas en frontend y backend
- Privacidad del teléfono configurable por usuario; el propio usuario y los administradores de su club pueden verlo
- El apodo solo reemplaza el nombre visible cuando el usuario activa esa preferencia; se conservan los nombres legales en la ficha
- Auditoría de acciones relevantes
- Visibilidad de clases: un deportista solo ve clases de su club que no tienen grupo o que pertenecen a su mismo grupo; un entrenador solo ve y gestiona las clases asignadas a él
- Los documentos de verificación del club y los comprobantes de pago se almacenan fuera de las rutas públicas

## 8. Plan de desarrollo recomendado

### Etapa 1: base
- Inicializar proyecto Django
- Configurar settings y base de datos
- Definir auth y roles
- Crear migraciones base

### Etapa 2: entidades de negocio
- Clubes, usuarios, deportistas y entrenadores
- Asignaciones y perfiles de usuario

### Etapa 3: entrenamiento y asistencia
- Grupos, actividades, clases disponibles y calendario
- Reserva y cancelación de cupos por deportistas, respetando la capacidad de cada clase
- Registro de asistencia efectiva por parte del entrenador; reservar un cupo no equivale a asistir
- Evitar reservas duplicadas y sobrepasar la capacidad de una clase

### Etapa 4: seguimiento deportivo
- Plantel general y equipo de competidores, evaluaciones, récord de peleas, historial de peso y evolución

### Etapa 5: tienda del gimnasio
- Catálogo y stock por club
- Carrito, pedidos y estado de pago/entrega
- Checkout integrado con proveedor de pago configurado y confirmación por webhook

### Etapa 5: analítica y alertas
- Dashboard, análisis rule-based y notificaciones internas

### Etapa 6: reportes y pruebas
- Exportación, reportes y test suite

### Etapa 7: UX y despliegue
- Responsive design, PWA, documentación y preparación de despliegue

## 9. Decisiones clave

- Se usarán módulos por dominio para mantener la escalabilidad y facilitar la defensa del proyecto.
- La gestión de usuarios y clubes se resolverá con una estructura de autorización robusta desde el backend.
- Cada entidad vinculada a un club deberá incluir una referencia explícita al club para garantizar aislamiento de datos.
- Los dashboards y alertas se construirán desde datos reales, nunca valores artificiales.

## 10. Lineamientos de mejora y estado (prompt maestro)

Reglas de trabajo: conservar el proyecto existente (no recrear módulos, no borrar datos, migraciones compatibles), validar permisos y precios siempre en el backend, aislar los datos por club y no declarar terminada una función sin probarla.

| Área | Estado | Detalle |
| --- | --- | --- |
| Membresías y planes por club | Implementado (base) | Planes, solicitud, confirmación manual del pago, vencimiento, historial, límite semanal de clases en reservas y pruebas. Opción por club "Exigir membresía activa para reservar clases" implementada (desactivada por defecto). Falta renovación y registro de cambios de planes. |
| Pagos de membresías | Implementado, sin validar con Mercado Pago real | Compra online con webhook firmado, verificación contra la API, idempotencia y activación solo tras pago aprobado (33 pruebas con proveedor simulado), web y móvil. Falta probar en el sandbox de Mercado Pago con credenciales de prueba y una URL pública. Sin cobros recurrentes. |
| Tienda y carrito | Parcial | Backend ya valida stock, precios y vencimiento de reservas. Carrito del frontend corregido. Falta revisar visualmente imágenes/etiquetas en móvil y estado de entrega. |
| Clases y reservas | Parcial | Cupos, duplicados y visibilidad por grupo funcionan. Falta disciplinas, horarios recurrentes y lista de espera. El límite semanal del plan ya se aplica. |
| Deportista a competidor | Implementado (base) | El entrenador solicita, el admin del club aprueba o rechaza; queda registro y notificaciones. Pruebas incluidas. |
| Combates entre clubes | Implementado (base) | Propuesta, confirmación del club rival, cancelación y resultado en un único registro compartido; pruebas incluidas. Falta calendario público y ranking. |
| Registro de clubes | Parcial | Verificación con documento y estados existe. Falta RUT, responsable y selección visual de disciplinas con revisión administrativa explícita. |
| Notificaciones | Parcial | Internas existentes; membresías ya notifican. Faltan vencimientos próximos y estados de pedidos. |
| Aplicación móvil | En progreso | `mobile/` (Expo + React Native) con sesión, clases, reservas, membresías, combates y tienda; falta probar en dispositivo físico/emulador nativo y las herramientas del entrenador (asistencia, evaluaciones). |
| Responsive y UX | Pendiente de auditoría | Revisar tablas, modales y navegación en móvil. |

## Empezar desde cero (reiniciar datos de desarrollo)

- Hacer una copia de `backend/db.sqlite3` y luego, en `backend`, ejecutar `python manage.py flush --no-input`. Esto borra usuarios, clubes, deportistas, clases, etc.; los roles se vuelven a crear solos al registrar un club.
- Registrar un club desde la pantalla de registro (queda `PENDING`) y crear un superusuario con `python manage.py createsuperuser` para aprobar clubes desde el panel de administración global.
- Los archivos `db.sqlite3.bak-*` son respaldos locales y no deberían subirse a Git.

## Correr codigo

- Terminal Frontend
    - cd /d C:\Users\renat\Desktop\Boxtrack\Boxtrack\frontend
    - npm install
    - npm run dev

- Terminal Backend
    - cd /d C:\Users\renat\Desktop\Boxtrack\Boxtrack\backend
    - python manage.py migrate
    - python manage.py runserver


## Subir a Github

- git add .
- git commit -m "nombre de commit"
- git push


## Correr en otra pc

- Instalar Git, Python 3.11–3.12 y Node.js 20.19+ o 22.12+. Después, abrir PowerShell
-   git clone <https://github.com/RenatoCielo/BoxTrack.git>
    cd Boxtrack
    Copy-Item .env.example .env

Para desarrollo local se usa SQLite por defecto. Para conectarse a MySQL, configura sus credenciales en `.env` y establece `USE_SQLITE_FALLBACK=False`.

En una terminal para el backend:

    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py runserver

En otra terminal, desde la carpeta raíz del proyecto:

    cd frontend
    npm install
    npm run dev