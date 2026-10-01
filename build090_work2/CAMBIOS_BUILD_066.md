# PAQUETE COMPLETO — BUILD 065 + BUILD 066

Este paquete reúne los arreglos de auditoría anteriores y los cambios nuevos de horarios y panel administrador.

Incluye:
- Compatibilidad PostgreSQL/Supabase y psycopg[binary].
- Guardado de apariencia, logos, fondos e iconos de premios.
- Correcciones del panel cliente, sesiones y consultas PostgreSQL.
- Cámara QR en ventana modal y fallback de código manual.
- Horarios normalizados para siete días.
- 00:00–00:00 interpretado como abierto todo el día.
- Sucursales en modo heredar sin horarios personalizados antiguos.
- Carga del administrador resistente a fallos aislados y mensajes HTTP claros.

La base de datos existente no se elimina ni se reemplaza.
