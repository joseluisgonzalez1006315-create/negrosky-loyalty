# Auditoría PostgreSQL / Render

## Correcciones incluidas

- Se agregó `psycopg[binary]==3.2.3` a `requirements.txt`. Sin esta línea Render no instala el controlador y el servidor falla con `ModuleNotFoundError: No module named 'psycopg'`.
- Se corrigieron las expresiones `MAX(valor, 0)` del panel de cliente a `GREATEST(valor, 0)`. PostgreSQL usa `MAX()` como función agregada y no acepta la forma de dos argumentos.
- El diagnóstico `/api/system/diagnostics` ya no ejecuta `PRAGMA integrity_check` cuando la aplicación está conectada a PostgreSQL.
- La consulta de negocios ya usa `LOWER(name)` en lugar de `COLLATE NOCASE`.
- La consulta de boletas pendientes ya no usa `json_each()`; usa `jsonb_array_elements_text()` cuando corresponde a PostgreSQL.

## Revisiones realizadas

La capa de compatibilidad existente ya convierte estos patrones del código antiguo: `?` a `%s`, `BEGIN IMMEDIATE` a `BEGIN`, `INSERT OR IGNORE` a `ON CONFLICT DO NOTHING`, `strftime(...,'now')` a `CURRENT_TIMESTAMP`, `GROUP_CONCAT` a `string_agg` y `last_insert_rowid()` a `lastval()`.

Los `PRAGMA table_info(...)` están dentro de `init_db()` y esa función sale inmediatamente cuando existe `DATABASE_URL`; por eso no se ejecutan contra Supabase en el arranque actual. Los `INSERT OR REPLACE` encontrados están solo en scripts de carga de datos (`seed_many_businesses.py`), no en las rutas normales del dashboard. Si se ejecuta ese script contra PostgreSQL habrá que convertirlo a `INSERT ... ON CONFLICT DO UPDATE` con el índice único correspondiente.
- Se corrigió la inicialización de módulos: PostgreSQL considera dos `NULL` distintos en una restricción `UNIQUE`, por lo que `INSERT OR IGNORE` podía duplicar módulos con `branch_id` vacío en cada reinicio. Ahora se verifica la existencia antes de insertar.

## Correcciones adicionales de esta revisión

- Se corrigió la conversión de `IS ?` a PostgreSQL. Esto era la causa por la que el formulario de horarios no podía cargar ni guardar filas con `branch_id` vacío.
- El escáner del trabajador ahora usa una capa fija de pantalla completa, video adaptado al celular, recuadro de enfoque, botón visible para cerrar, liberación de la cámara al salir de la página y cancelación del bucle de lectura.
- Se aumentó la resolución solicitada a la cámara y se mantuvo el lector `BarcodeDetector`/`jsQR` como respaldo.
- Se actualizaron las versiones de caché de `worker.html` para que el navegador descargue el código nuevo.
