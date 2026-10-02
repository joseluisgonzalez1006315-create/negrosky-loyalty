# Build 150 · Notificaciones corregidas

- Corrige el error al abrir el panel de notificaciones cuando `created_at` está almacenado como texto en PostgreSQL.
- Convierte el valor a texto antes de aplicar la fecha de respaldo.
- Conserva el formato de fechas del historial y notificaciones del Build 149.
