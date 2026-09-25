# CAMBIOS · BUILD 023

## Iconos y categorías de fidelización

- Se conserva el emoji existente como opción predeterminada.
- Se agregaron categorías de iconos para comida, belleza, mascotas, deportes y servicios.
- Se puede subir un icono propio por campaña en PNG, JPG o WebP de máximo 1 MB.
- El icono se valida por extensión declarada y firma real del archivo.
- Se puede reemplazar o quitar el icono sin afectar compras, ciclos ni premios.
- La vista previa y la lista administrativa muestran el icono cuando existe.
- La tarjeta del cliente usa automáticamente el icono en cada sello de progreso.

## Continuidad

- Los emojis, programas, compras, premios múltiples, stock, citas, QR y personalización visual de BUILD 019 se conservan.
- Los iconos se guardan dentro de SQLite y se incluyen en los respaldos.
- La tabla nueva se crea mediante migración automática.
