# CAMBIOS · BUILD 018

## Correcciones

- Se corrigió el sondeo inicial de notificaciones para dueños de negocio y administradores de sucursal. La consulta ahora entrega correctamente los parámetros de alcance a SQLite.
- Se evita el error repetitivo `Incorrect number of bindings supplied` que podía llenar el registro del servidor durante el sondeo automático.

## Pruebas

- Se agregó una prueba de regresión que inicia sesión como dueño de negocio y comprueba tanto el arranque del sondeo como la recepción de notificaciones.
- Se mantienen las pruebas existentes de aislamiento, permisos, fidelización, QR, citas, cancelaciones, demoras, respaldos y migraciones.

## Identidad de versión

- Se actualizaron el panel administrativo, el panel del trabajador, el Control Center, el instalador, el README y los archivos de versión a NEGROSKY LOYALTY V3 BUILD 018.
- Se conservaron los registros históricos de cambios de BUILD 013 a BUILD 017.

## Continuidad

- No se reconstruyó ningún módulo existente.
- La base de datos incluida se conserva sin cambios destructivos.
- Este BUILD queda preparado para iniciar el diseñador visual por negocio en la siguiente fase.
