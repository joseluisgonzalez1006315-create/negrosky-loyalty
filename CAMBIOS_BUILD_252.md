# Build 252 · experiencia visual del cliente

Continúa el rediseño sobre Build 251.

## Cambios

- Tarjetas de fidelización con jerarquía visual, línea de progreso y sombra más claras.
- Accesos rápidos del cliente con estados hover/focus más consistentes.
- Contenedores vacíos ocultos para evitar espacios o módulos visuales sin contenido.
- Módulos de horarios, reservas y rifas con separación y profundidad visual uniforme.
- Mejor adaptación de tarjetas y botones en Android, iPhone y pantallas pequeñas.
- No se cambiaron datos, permisos, endpoints ni procesos de compra, rifa o reserva.
- Cache busting actualizado a v252.

## Validación

- `node --check web/app.js`
- `python -m py_compile app/main.py main.py`
