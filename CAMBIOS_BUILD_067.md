# BUILD 067 — Estabilidad de Render y pantallas

Esta versión no modifica ni reemplaza la base de datos.

## Correcciones incluidas

- Notificaciones: se corrigió la consulta inicial para que, si todavía no hay notificaciones, devuelva `last_id: 0` sin lanzar un error ni afectar la pantalla.
- Rifas: la consulta de participaciones pendientes ya no se ejecuta cada dos segundos fuera de la vista de rifas. Solo se actualiza cuando esa vista está abierta y cada 15 segundos.
- PWA: se agregó el ícono estático que faltaba y ocasionaba el `404` en Render.

## Validación realizada

- Compilación sintáctica de los archivos Python.
- Consulta de notificaciones validada con una tabla sin registros y con registros.
- Archivo del ícono y nueva regla de actualización de rifas verificados.

## Pendiente de prueba visual

Probar en Render el guardado de horarios y el diseño de la página con una captura o ruta concreta cuando la nueva versión esté publicada. El ZIP recibido no trae la base de datos publicada, por lo que no se modificó información real.
