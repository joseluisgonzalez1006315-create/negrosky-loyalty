# BUILD 214 · Reducción de consumo Supabase

- Se redujo la frecuencia de actualización de rifas del cliente de 15 s a 30 s.
- Se redujeron actualizaciones visuales internas de rifas que no consultan datos de 1.5–3 s a 10 s.
- Se redujo la revisión de participaciones pendientes del negocio de 10 s a 30 s.
- Se redujo la consulta de permisos del trabajador de 5 s a 30 s.
- Se redujo el sondeo de notificaciones del administrador de 10 s a 30 s.
- Se redujo la consulta automática del calendario administrativo de 20 s a 60 s.
- No se modificaron tablas, datos, autenticación ni rutas de validación.

El objetivo es disminuir la salida de datos de Supabase sin quitar las actualizaciones manuales ni la actualización inicial de cada pantalla.
