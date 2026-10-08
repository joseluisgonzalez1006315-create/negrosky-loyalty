# Build 255 · identidad y saludo del cliente

Continúa sobre Build 254.

## Cambios

- Saludo personalizado del cliente dentro de la portada después de iniciar sesión.
- Indicadores visuales de beneficios, premios y experiencia digital.
- Vista previa con el mismo saludo de ejemplo y los mismos indicadores.
- Ajustes de espaciado, contraste y lectura para la portada en celular y computador.
- No se modificaron endpoints, permisos, compras, rifas, reservas ni tablas.
- Caché actualizado a v255.

## Validación

- `node --check web/app.js`
- `node --check web/customer.js`
- `python -m py_compile app/main.py main.py`
