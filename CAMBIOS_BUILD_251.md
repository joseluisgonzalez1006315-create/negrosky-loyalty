# Build 251 · editor visual refinado

Continúa el rediseño administrativo sobre Build 250.

## Cambios

- Editor visual con mejor jerarquía, separación y contraste entre secciones.
- Acordeones del editor con estado abierto más evidente y lectura más clara.
- Indicador “Editor en vivo” y barra de guardado visual más clara.
- Selector Celular/Escritorio convertido en control segmentado.
- Controles de zoom y vista previa más compactos y consistentes.
- Galería de temas con estado seleccionado visible.
- Vista previa con marco, sombra y contraste mejorados sin cambiar su sincronización.
- Adaptación específica para pantallas pequeñas.
- No se cambiaron endpoints, permisos, consultas ni lógica de módulos.
- Cache busting actualizado a v251.

## Validación

- `node --check web/app.js`
- `python -m py_compile app/main.py main.py`
