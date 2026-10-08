# Build 242 · Selector de negocios de Estadísticas

- Se eliminó el filtro adicional `deleted_at` que podía descartar todos los negocios cuando la respuesta no lo entregaba como `null`.
- Estadísticas ahora muestra cualquier negocio devuelto por `/api/tenants`, excepto los estados `trashed` y `deleted`.
- Se conservó el reintento posterior a la sesión y el control único de navegación.
- Se actualizaron versión y caché a 242.
- No se modificaron los demás módulos ni la base de datos.
