# Build 249 · sincronización de módulos

## Corrección
El panel de Módulos por negocio solo actualizaba las casillas cuando se cambiaba a otro negocio. Si el negocio activo ya estaba seleccionado, se conservaban las casillas HTML iniciales sin marcar.

Ahora la configuración se vuelve a leer al abrir el módulo, al cambiar de negocio y al reaplicar el negocio activo. También se normalizan valores booleanos antiguos de SQLite/PostgreSQL.

## Validación
- `node --check web/app.js`
- `python3 -m py_compile app/main.py main.py`
- Cache busting de recursos y Service Worker a v249.
