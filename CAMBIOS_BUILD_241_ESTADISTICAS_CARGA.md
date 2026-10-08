# Build 241 · Carga resistente de Estadísticas

- El selector de negocios acepta los negocios vigentes aunque el backend entregue el estado con otra capitalización o formato.
- Se añadió un reintento corto después de la sesión para evitar que el selector quede vacío por una carrera de carga.
- Se muestra “No hay negocios activos disponibles” cuando la respuesta realmente no contiene negocios.
- La navegación quita el foco del botón y evita que Estadísticas parezca seleccionada por foco o reglas CSS antiguas.
- Se eliminaron pseudoiconos duplicados para Estadísticas.
- Se conserva la protección de permisos y no se modifican otros módulos.
