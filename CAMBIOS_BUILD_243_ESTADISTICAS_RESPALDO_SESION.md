# Build 243 · Estadísticas usa el negocio de la sesión

- Si `/api/tenants` tarda o el selector aún no tiene opciones, Estadísticas crea una opción temporal con el `tenant_id` de la sesión.
- `loadAnalytics()` ahora siempre usa como respaldo `currentMe.tenant_id`, por lo que consulta `/api/analytics` en lugar de abandonar con selector vacío.
- Cuando la lista completa de negocios llega, reemplaza la opción temporal y conserva el negocio activo.
- Se actualizaron versión y caché a 243.
- No se modificaron permisos, base de datos ni otros módulos.
