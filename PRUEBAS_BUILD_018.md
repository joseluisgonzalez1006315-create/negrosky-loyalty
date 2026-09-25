# PRUEBAS · BUILD 018

## Resultado de regresión

- 12 pruebas automatizadas superadas.
- 2 pruebas de QR no se ejecutaron en el entorno de auditoría porque el paquete contiene Pillow compilado para Windows y la auditoría se realizó en Linux.
- La sintaxis de Python y JavaScript fue validada.

## Corrección verificada

- El sondeo inicial de notificaciones responde correctamente para el superadministrador.
- El sondeo inicial y la recepción de avisos responden correctamente para el dueño de negocio.
- La consulta conserva el aislamiento por negocio y sucursal.

## Pruebas físicas pendientes

- Cámara y QR en Android.
- Cámara, permisos y sonido en Safari para iPhone.
- Ejecución prolongada del servidor en Windows.
