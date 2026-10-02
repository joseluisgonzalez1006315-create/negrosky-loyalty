# CAMBIOS BUILD 044

## Actualización ligera y continuidad automática

1. Se conserva la funcionalidad de BUILD 041 sin reconstruir módulos existentes.
2. El instalador busca automáticamente la versión anterior en la misma carpeta principal.
3. Reutiliza el entorno `venv` para evitar reinstalar dependencias.
4. Recupera automáticamente la base de datos `data/negrosky_v2.db`.
5. Recupera automáticamente la carpeta `backups` de la versión anterior.
6. Se actualizan las referencias activas a BUILD 044 y versión 3.0.44.

## Orden recomendado

1. Extraer BUILD 044 al lado de la versión anterior.
2. No borrar la versión anterior.
3. Ejecutar `INICIAR_NEGROSKY.bat` dentro de BUILD 044.
4. Verificar `/api/health`, administrador, trabajador y páginas de clientes.
5. Cuando todo esté confirmado, conservar la versión anterior como respaldo.

Esta build no elimina datos ni sobrescribe la versión anterior.
