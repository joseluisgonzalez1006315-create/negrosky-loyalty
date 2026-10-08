# Build 253 · rediseño visible del cliente

Continúa sobre Build 252 sin cambiar la lógica de datos.

## Cambios

- Cabecera pública del negocio con mayor jerarquía visual, profundidad y línea de identidad.
- Barra de accesos del cliente más visible en computador y celular.
- Accesos rápidos con estados, tamaños y contraste uniformes.
- Encabezados visuales para progreso y premios cuando existen campañas.
- Tarjetas de fidelización, perfil, reservas, horarios y rifas con separación y profundidad coherentes.
- Vista previa del editor alineada con la nueva jerarquía visual de la página real.
- Ajuste responsive para Android, iPhone y computador.
- No se cambiaron endpoints, permisos, compras, rifas, reservas ni tablas.
- Cache busting actualizado a v253.

## Validación

- `node --check web/app.js`
- `python -m py_compile app/main.py main.py`
