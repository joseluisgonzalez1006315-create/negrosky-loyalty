# Cambios BUILD 023

## Corrección de personalización en la vista del cliente

- La página pública ahora consulta la configuración con `cache: no-store`.
- Los cambios de logo, colores, fondo, botones y textos se aplican sin tener que cerrar la página.
- La configuración se vuelve a revisar automáticamente cada 5 segundos mientras el cliente mantiene abierta su tarjeta.
- Si se elimina el logo, vuelve a mostrarse la inicial del negocio.
- Se añadieron mensajes de consola para detectar errores de carga de personalización.

## Corrección de creación de negocios

- Se mantiene la creación mediante `/api/tenants` y se conserva la validación de URL corta.
- Los mensajes de error del formulario se muestran directamente para identificar duplicados, permisos o datos inválidos.

