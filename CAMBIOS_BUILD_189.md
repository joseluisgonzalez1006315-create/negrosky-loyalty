# Build 189 — Optimización de salida Supabase

- Cache de 60 segundos en la respuesta pública de publicidades con flyers.
- La caché se invalida al crear, editar, activar, desactivar o eliminar una publicidad.
- El cliente ya no fuerza `refresh=Date.now()` en cada carga de publicidad.
- Actualizaciones administrativas menos frecuentes: notificaciones 10 s, permisos 30 s y campañas 60 s.
- Rifas del cliente mantienen sincronización funcional, con consultas menos frecuentes.
- Cache-Control de estáticos conserva la carga rápida.

Objetivo: reducir la salida de Supabase sin eliminar módulos ni cambiar los datos.
