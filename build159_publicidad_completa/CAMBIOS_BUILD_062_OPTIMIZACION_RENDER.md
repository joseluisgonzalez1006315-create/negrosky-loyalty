# Build 062 — Optimización de carga

- La página pública entrega el HTML inicial sin esperar una consulta de base de datos.
- La página del cliente evita mostrar primero el tema predeterminado y carga la personalización antes de mostrar el contenido.
- Se eliminaron peticiones duplicadas del cliente y se retrasaron fondos, rifas y módulos secundarios.
- Se reutilizan conexiones PostgreSQL mediante un pool pequeño para reducir la latencia de Supabase/PostgreSQL.
- Se habilitó compresión GZip para HTML, JavaScript, CSS y JSON grandes.
- Se añadieron cachés seguros para archivos estáticos, branding, logos, fondos e iconos.
- Se conserva el soporte de negocios generales sin sucursal y los QR con sucursal.
- Render usa `PUBLIC_BASE_URL=https://negrosky-loyalty.onrender.com` para generar enlaces estables.

No se modifican ni se eliminan datos de la base de datos.
