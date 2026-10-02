# Build 151 · Fechas de notificaciones corregidas

- El panel de notificaciones usa ahora el mismo parser robusto del historial.
- Reconoce fechas PostgreSQL con `+00`, `+0000`, `+00:00`, milisegundos y fechas sin zona horaria.
- Mantiene el respaldo de fecha del servidor para registros antiguos.
