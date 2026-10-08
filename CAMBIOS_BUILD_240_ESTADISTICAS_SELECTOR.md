# Build 240 · Corrección final de Estadísticas

- Se eliminó el resaltado visual permanente de Estadísticas.
- Estadísticas conserva el estado `active` exclusivamente cuando su vista está visible.
- El selector de negocios ya no depende de un filtro prematuro que podía dejarlo vacío.
- Se excluyen únicamente negocios eliminados o enviados a papelera.
- Se conserva la carga posterior a `/api/me`, `/api/tenants`, `currentMe` y `tenants`.
- No se modificaron reservas, rifas, fidelización, clientes, usuarios, publicidad, permisos ni base de datos.

Validaciones: `node --check web/app.js`, `python3 -m py_compile app/main.py main.py`, una vista y un botón de Estadísticas, y una sola definición de `showAdminView`.
