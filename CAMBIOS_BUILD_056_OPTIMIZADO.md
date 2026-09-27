# BUILD 056 OPTIMIZADO

Cambios aplicados sobre el ZIP de GitHub recibido:

- Se actualizó la versión del backend y el diagnóstico a BUILD 056.
- Los archivos estáticos versionados pueden permanecer en caché durante 24 horas; las respuestas de API y HTML siguen sin caché.
- Se eliminó la consulta automática del estado de salud cada 30 segundos al abrir el panel. El diagnóstico se consulta al abrir la sección correspondiente o al pulsar su botón.
- Se corrigió la caché interna del panel: después de cualquier POST, PUT o DELETE se limpian las respuestas GET almacenadas. Esto evita que el editor de diseño muestre datos antiguos después de guardar.
- La ruleta quedó retirada del alcance. Se ocultan sus controles antiguos y el backend rechaza el módulo aunque exista una configuración antigua.
- Se actualizaron las referencias visibles de BUILD 055 a BUILD 056 y los identificadores de caché de los recursos web.
- Se redujeron varias actualizaciones automáticas del panel que podían repintar la interfaz innecesariamente.

## Verificaciones realizadas

- Compilación de todos los archivos Python: correcta.
- Comprobación de sintaxis JavaScript de `app.js`, `customer.js` y `scope-fixes.js`: correcta.
- Se conservó la estructura original del proyecto y no se incluyeron datos locales del paquete pesado.

## Límite de esta comprobación

La conexión real con Supabase/Render y los flujos que requieren una sesión de administrador o datos productivos deben probarse después de subir el paquete. El ZIP original se conserva aparte como respaldo.
