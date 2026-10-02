# Build 149 · Fechas administrativas corregidas

- Acepta fechas PostgreSQL con zona horaria `+00`, `+0000` y `+00:00`.
- Mantiene milisegundos y fechas sin zona horaria.
- El historial administrativo conserva y muestra las fechas de compras y premios.
- Las notificaciones reciben una fecha de respaldo desde el servidor cuando el registro antiguo no tenía `created_at`.
- No cambia datos, tablas, rifas, autenticación ni permisos.
