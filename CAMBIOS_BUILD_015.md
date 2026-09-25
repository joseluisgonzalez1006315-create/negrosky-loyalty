# CAMBIOS · BUILD 015 DEMO

## Terminado

- Agenda de citas activable por negocio o sucursal.
- Servicios configurables con nombre, duración, precio y sucursal.
- Reserva desde la página del cliente, validación de horario y bloqueo de cruces.
- Agenda privada para dueño/administrador con estados: programada, confirmada, completada, cancelada o no asistió.
- Notificaciones internas de compras, premios y citas, con contador y opción de marcar como leídas.
- Detección automática de la URL desde donde se abre la plataforma.
- URL general de administrador/trabajador y una URL de cliente separada por cada negocio con su nombre.
- Exclusión de direcciones virtuales comunes para evitar mostrar enlaces que no abren en el celular.
- Negocios, sucursales y clientes ordenados alfabéticamente.
- Aislamiento reforzado: cada dueño solo ve su negocio, clientes, trabajadores, citas, campañas, movimientos y notificaciones.

## Comprobado

- 10 pruebas automatizadas aprobadas.
- Dos negocios de prueba no pueden consultar información entre sí.
- Clientes ordenados correctamente aun con mayúsculas y tildes.
- Reserva de cita, detección de horario ocupado, cambio de estado y notificación.
- URL de todos los negocios, filtradas según el rol.
- Sintaxis Python y JavaScript correcta.

## Pendiente

- Venta/control de tiempo.
- Diseñador visual completo, temas, imágenes, fondos y formas.
- Notificaciones externas por WhatsApp, correo o push.
- Ocho negocios demo completos.
- Más idiomas, países, monedas y zonas horarias.
- Aplicaciones instalables y publicación definitiva con HTTPS.
