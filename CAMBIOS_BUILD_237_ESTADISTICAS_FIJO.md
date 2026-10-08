# Build 237 · Estadísticas visible desde el menú base

- Estadísticas ahora está declarada directamente en `web/index.html`, junto a Notificaciones.
- El montador dinámico evita duplicarla y conserva la pantalla, filtros y métricas existentes.
- Actualiza caché y versión para evitar que el navegador conserve el menú anterior.
- No cambia permisos, datos ni lógica de otros módulos.
