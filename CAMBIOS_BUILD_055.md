# BUILD 055 · CONTROL CENTRAL DE MÓDULOS

## Qué cambia

- El Administrador General puede seleccionar un negocio y activar o desactivar sus módulos.
- El dueño del negocio no recibe el catálogo de funciones ocultas.
- Los módulos ocultos desaparecen del menú y quedan bloqueados también en el backend.
- Al desactivar Página pública, también se cierran la página, el QR y los endpoints públicos del negocio.
- Citas, venta por tiempo y notificaciones validan el permiso en sus rutas administrativas y de operación.
- Se incorporan al catálogo: Fidelización, Agenda, Venta por tiempo, Notificaciones, Página pública, Rifas y Ruleta.
- La configuración de horarios queda separada del control central de módulos.
- Se registra en auditoría quién cambió las funciones de cada negocio.
- Se mantiene el control opcional por sucursal para futuras configuraciones avanzadas.
- El negocio elegido en “Módulos por negocio” queda sincronizado con el negocio activo; ya no se muestran por error los módulos de otro negocio.
- El control del Administrador General queda cerrado mientras carga el estado real del negocio, evitando mostrar módulos por defecto durante una consulta lenta.
- Agenda y Ruleta quedaron fuera de Fidelización en la página del cliente; una respuesta tardía no puede volver a mostrar Agenda después de desactivarla.
- Se actualizan las versiones de caché de las tres interfaces para evitar reutilizar JavaScript de una build anterior.
- El iniciador y el Control BUILD 055 verifican la versión real de `/api/health`; si el puerto 8030 tiene un servidor NEGROSKY anterior, lo cierran antes de arrancar esta build. Un proceso ajeno que use el puerto no se toca.
- El encabezado de administración y el panel de trabajador ahora muestran BUILD 055 desde el HTML inicial, antes de que cargue JavaScript.
- Se corrige la regla visual de la Ruleta: `display:block!important` estaba anulando `.hidden!important`; ahora solo se fuerza la visualización cuando la Ruleta no tiene la clase `hidden`.
- La navegación del panel ahora fuerza una única vista activa; Horarios, Diseño visual, Fidelización y los demás apartados no pueden quedar visibles simultáneamente.
- Los módulos operativos quedan organizados por su propio estado: campañas de Fidelización, servicios de Reservas, servicios de Venta por tiempo, cierre temporal de Horarios y configuraciones de Ruleta pueden activarse o pausarse desde su zona correspondiente. El permiso maestro continúa bajo control del Administrador General.
- Ruleta incorpora guardado real de estado ACTIVA/PAUSADA y auditoría del cambio.

## Pruebas realizadas

- Compilación de app/main.py y app/schemas.py.
- Migración segura de módulos existentes mediante INSERT OR IGNORE.
- Aislamiento de permisos para super_admin y business_admin.
- Ocultamiento de rifas y ruleta cuando el módulo está desactivado.
- Verificación de arranque, página pública y bloqueo de módulos opcionales con respuestas sin revelar el catálogo.
- Prueba real con PIZZAS y Santuario Granizados: selección, guardado, persistencia y menú correspondiente al negocio seleccionado.
- Prueba real del cliente con módulos apagados y Página pública apagada mientras la página ya estaba abierta.
- Prueba real del trabajador con Fidelización, Citas y Venta por tiempo apagados y reactivados sin cerrar la página.
