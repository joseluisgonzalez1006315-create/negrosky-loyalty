# Build 239 · Estadísticas integrada

## Qué se corrigió

- Estadísticas ahora tiene un único botón `data-view="analytics"` y una única vista `view-analytics` declarada en `web/index.html`.
- Se eliminó el montaje dinámico y el script de respaldo que podían crear una vista vacía o eventos duplicados.
- La navegación usa un único controlador: la vista visible y el botón `active` se actualizan juntos al cambiar de módulo.
- El módulo carga el negocio activo, periodo, métricas, visitas diarias, eventos para el administrador general y campañas.
- Se añadieron estados de carga, error y ausencia de datos.
- Actualizar, cambiar negocio y cambiar periodo vuelven a consultar `/api/analytics` sin recargar la página.
- Los controles visuales se adaptaron al diseño actual del panel y a móvil.
- Se conservaron los permisos existentes: solo `super_admin` puede editar o borrar totales mediante los endpoints existentes.

## Archivos modificados

- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `app/main.py`
- `main.py`
- `VERSION.txt`

## Validaciones ejecutadas

- `node --check web/app.js`
- `python3 -m py_compile app/main.py main.py`
- Una sola vista `view-analytics` en el HTML.
- Un solo botón `data-view="analytics"` en el HTML.
- Una sola definición de `showAdminView`.
- Sin montaje dinámico ni fallback duplicado para Estadísticas.

La prueba de inicio de sesión y carga contra el servidor remoto debe repetirse después de subir este ZIP, porque requiere la sesión y los datos de la instancia desplegada.
