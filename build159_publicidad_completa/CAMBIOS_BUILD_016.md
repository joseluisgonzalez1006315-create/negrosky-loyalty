# CAMBIOS · BUILD 016 DEMO

## Terminado

- Cliente elige fecha y hora en la agenda; solo puede reservar las horas libres. Las ocupadas se muestran como «Ocupada» y quedan deshabilitadas. Se indica cuando un día no tiene cupos.
- Cuando no quedan citas ese día, se indica la siguiente fecha disponible y se ofrece un botón para seleccionarla.
- Crear servicios generales también funciona cuando el módulo de citas está activado solo para una sucursal. Si no hay servicios, el cliente ve un aviso en vez de un formulario que parece vacío.
- La reserva verifica nuevamente el horario bajo una transacción para impedir que dos clientes confirmen a la vez el mismo espacio.
- El QR generado desde la PC usa la dirección local del servidor y abre `/worker?code=...` en el celular; el enlace para compartir utiliza la misma dirección. Se evitan direcciones virtuales comunes.
- Avisos de compras, premios y citas en la parte inferior del panel, y avisos del cliente en su página; aparecen con una consulta cada tres segundos y desaparecen automáticamente. Los errores y confirmaciones de operaciones también se muestran abajo.
- El servidor filtra las notificaciones según el negocio, la sucursal y el cliente. Se respeta el módulo de notificaciones activable por negocio o sucursal.
- Se conservan los cambios y datos de BUILD 015. El iniciador puede copiar la base anterior al abrir esta carpeta por primera vez.

## Comprobado

- 12 pruebas automatizadas aprobadas: URL del QR y código, disponibilidad, creación de citas, día completo con sugerencia del siguiente, módulo por sucursal, separación entre negocios y avisos por cliente, además de los flujos anteriores.
- Sintaxis JavaScript de panel, cliente, trabajador y avisos verificada.
- La URL móvil necesita que el teléfono y la PC puedan comunicarse por la misma red Wi-Fi y que el firewall permita el puerto 8030. La cámara física de un iPhone o Android no se puede emular en estas pruebas.

## Pendiente

- Venta y control de tiempo.
- Diseñador visual, imágenes, logos, fondos, plantillas y previsualización.
- Notificaciones externas por WhatsApp, correo o push; los avisos de esta versión funcionan con la página abierta.
- Ocho negocios completos de demostración.
- Más idiomas, países y monedas; publicación con HTTPS y acceso fuera de la red local.
