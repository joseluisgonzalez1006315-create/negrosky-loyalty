# NEGROSKY LOYALTY V3 — BUILD 047.1

## Venta y control de tiempo

- Migraciones automáticas para `time_services` y `time_sessions`.
- Panel para crear, activar o desactivar servicios por minutos u horas.
- Control de sesiones abiertas e historial administrativo.
- El trabajador puede buscar un cliente, iniciar una sesión y cerrarla desde `/worker`.
- Cada sesión guarda negocio, sucursal, cliente, trabajador, inicio, final, minutos usados y precio.
- Sesiones simultáneas para clientes distintos; un cliente no puede tener dos sesiones abiertas.
- Validación de módulo activo, horario, negocio y sucursal.
- Auditoría y notificaciones internas al iniciar/cerrar sesiones.

## Compatibilidad

- No se eliminó ninguna función previa.
- La migración corre automáticamente al iniciar el servidor con una base existente.
- Se incluye respaldo previo: `backups/negrosky_pre_build_047.db`.

## BUILD 048 · Corrección inicial

- Las sesiones que superan `planned_end_at` se cierran automáticamente al consultar el módulo.
- El cliente recibe una notificación interna cuando su tiempo finaliza.
- Se agregó el endpoint privado `/api/public/me/time-sessions` para consultar sesiones propias.
- Antes de iniciar una nueva sesión se regulariza cualquier sesión vencida del mismo cliente.
- Cada sesión devuelve también `remaining_minutes` para mostrar el tiempo restante en los paneles.

## BUILD 049 · Validación multi-negocio

- Se impide crear servicios usando sucursales de otro negocio.
- Se impide iniciar sesiones usando sucursales que no pertenecen al negocio activo.
- La versión reportada por el backend y el diagnóstico pasa a `3.0.49` / BUILD 049.
- Se conserva la compatibilidad con los módulos y pruebas previamente validados.

## BUILD 050 · QR y acceso por sucursal

- Los QR de compra y premios guardan la sucursal de origen.
- La vista previa y validación rechazan QR pertenecientes a otra sucursal.
- Migración automática segura para instalaciones existentes.

## BUILD 050.1 · Identidad visual del trabajador

- El panel del trabajador muestra negocio, sucursal y usuario activo.
- Se aplica logo, color principal y color secundario configurados por el negocio.
