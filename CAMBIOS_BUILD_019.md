# CAMBIOS · BUILD 019

## Diseñador visual

- Nueva pestaña Diseño visual para personalizar cada negocio de forma independiente.
- Configuración de nombre visible, mensaje de bienvenida, color principal, color secundario, color de botones y fondo.
- Fondos oscuro, claro y de color personalizado.
- Tarjetas con estilo suave, sólido o cristal.
- Vista previa en vivo antes de guardar.

## Logos

- Carga de logos PNG, JPG y WebP de máximo 2 MB.
- Validación del tipo declarado y de la firma real del archivo.
- Opción para quitar el logo y recuperar la marca N predeterminada.
- El logo se guarda en SQLite para mantenerse dentro de las copias de seguridad.

## Compatibilidad y seguridad

- Migración automática mediante la tabla business_branding sin alterar los datos existentes.
- Personalización aplicada en la vista del cliente para PC, Android y iPhone mediante navegador.
- El superadministrador y el dueño pueden editar; el administrador de sucursal puede consultar sin modificar.
- Colores validados en formato hexadecimal y textos con límites de longitud.

## Continuidad

- Se mantienen las funciones de BUILD 018, incluida la corrección del sondeo de notificaciones.
- No se reconstruyeron fidelización, premios, QR, citas, clientes ni respaldos.
