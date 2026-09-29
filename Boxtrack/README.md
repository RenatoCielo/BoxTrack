# BOXTRACK

Plataforma de gestión y seguimiento deportivo para clubes y academias de boxeo.

## Descripción
BoxTrack centraliza la información de deportistas, entrenadores, entrenamientos, asistencia, evaluaciones, competiciones y alertas de seguimiento, con foco en clubes pequeños y medianos. La solución está diseñada para reemplazar los registros dispersos en WhatsApp, Excel y cuadernos por una plataforma ordenada, segura y con métricas útiles para la planificación deportiva.

## Visión arquitectónica

- Backend: Python + Django + Django REST Framework
- Frontend: React + Vite + JavaScript
- Base de datos: MySQL
- Autenticación: JWT con control de acceso por roles
- Visualización: Recharts + Lucide React
- Estilo: responsive, mobile-first, accesible y preparado para PWA
- Seguridad: aislamiento por club, permisos por rol, validación server-side, rutas protegidas

## Arquitectura propuesta

- Capa frontend: SPA en React para dashboard, gestión, reportes y fichas deportivas.
- Capa backend: API REST con módulos por dominio y servicios de negocio.
- Capa datos: MySQL con modelos relacionales normalizados y migraciones de Django.
- Capa de seguridad: JWT, permisos por rol, middleware de club y validación de acceso.

## Estructura inicial del proyecto

```text
Boxtrack/
├── README.md
├── .env.example
├── .gitignore
├── docs/
│   └── arquitectura-boxtrack.md
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── boxtrack_api/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── apps/
│       ├── __init__.py
│       ├── accounts/
│       ├── clubs/
│       ├── athletes/
│       ├── trainers/
│       ├── groups/
│       ├── trainings/
│       ├── attendance/
│       ├── evaluations/
│       ├── weight_tracking/
│       ├── competitions/
│       ├── alerts/
│       ├── notifications/
│       ├── dashboard/
│       ├── reports/
│       └── common/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── services/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       └── styles/
└── docs/
```

## Plan de desarrollo por etapas

1. Etapa 1: configuración, base de datos, autenticación y roles.
2. Etapa 2: clubes, usuarios, deportistas y entrenadores.
3. Etapa 3: grupos, entrenamientos, calendario y asistencia.
4. Etapa 4: fichas deportivas, evaluaciones y peso.
5. Etapa 5: análisis, alertas, histórico competitivo y dashboards.
6. Etapa 6: reportes, notificaciones, pruebas y seguridad.
7. Etapa 7: diseño responsive, PWA, documentación y despliegue.

## Modelos clave

- Club
- Usuario
- Rol y permisos
- Deportista
- Entrenador
- Grupo
- Asignación
- Entrenamiento
- Actividad
- Asistencia
- Evaluación deportiva
- Registro de peso
- Combate / competencia
- Alerta
- Notificación
- Objetivo deportivo

## Requisitos

- Python 3.11+
- Node.js 18+
- MySQL 8.0+
- VS Code con extensiones de Python y JavaScript

## Instalación rápida

1. Crear entorno virtual de Python.
2. Instalar dependencias del backend.
3. Configurar variables de entorno desde .env.example.
4. Crear base de datos MySQL.
5. Ejecutar migraciones.
6. Instalar dependencias del frontend.
7. Ejecutar backend y frontend.

## Tienda del gimnasio

El administrador agrega productos desde **Tienda**, incluyendo precio y stock. Los usuarios autenticados pueden armar un carrito y crear pedidos; el stock se reserva al confirmar, y se libera al cancelar o al vencer un checkout online.

Transferencia y pago presencial quedan como pedidos pendientes para confirmación del gimnasio. Para habilitar cobro con Mercado Pago, copia `.env.example` a `.env` en la raíz del proyecto y configura `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` y `MERCADOPAGO_NOTIFICATION_URL`. La URL de notificación debe ser pública y apuntar a `/api/store/payments/mercadopago/webhook/`; en desarrollo local puedes exponer el backend mediante un túnel HTTPS. Sin estas credenciales BOXTRACK desactiva el pago online y no simula cobros.

## Plantel competitivo

Los perfiles marcados como competidores aparecen en **Boxeadores competidores**, separados del plantel general. Se les puede asignar un grupo de preparación; las cuentas de deportista solo ven las clases generales y las de su grupo. El récord se calcula automáticamente como victorias-derrotas-empates desde el historial, sin contar sparring.

## Nota importante

Esta fase inicial crea la base del proyecto y la arquitectura recomendada para BOXTRACK. La funcionalidad real se desarrollará etapa por etapa, manteniendo una estructura modular y un diseño escalable para que Renato Cielo y Nicolás Merino puedan continuar el proyecto de manera ordenada.
