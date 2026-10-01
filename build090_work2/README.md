# NEGROSKY LOYALTY V3 · BUILD 055

Plataforma local multi-negocio de fidelización, preparada para computador y celular en la misma red Wi-Fi.

### Actualización 055 · Control central de módulos

- El Administrador General selecciona un negocio y decide qué funciones quedan activas.
- El dueño solo recibe las funciones activas; el catálogo oculto no se envía a su panel.
- El menú y el servidor aplican el mismo permiso para fidelización, citas, venta por tiempo, notificaciones, página pública, rifas y ruleta.
- Los cambios se guardan en la auditoría y la configuración de horarios queda separada.
- El iniciador comprueba `/api/health`; si encuentra un NEGROSKY viejo en el puerto 8030, lo identifica y lo reemplaza por BUILD 055. Si el puerto pertenece a otro programa, no lo toca y muestra el aviso.

### Actualización 047 · Venta y control de tiempo

- Servicios por minutos u horas, con duración y precio.
- Inicio y cierre de sesiones desde el panel del trabajador.
- Control administrativo de sesiones abiertas e historial.
- Alcance estricto por negocio y sucursal, con migración automática de SQLite.

### Actualización 049 · Seguridad y control de sesiones

- Validación de pertenencia de sucursales al negocio antes de crear servicios o sesiones.
- Cierre automático de sesiones vencidas y cálculo de `remaining_minutes`.
- Consulta privada del tiempo comprado por el cliente.
- Notificación interna al finalizar el tiempo.

### Actualización 050 · QR por sucursal

- Cada QR de compra o premio queda vinculado a la sucursal del cliente.
- Un trabajador no puede validar un QR generado para otra sucursal.
- La migración de `operation_tokens` agrega `branch_id` automáticamente.

### BUILD 050.1 · Identidad del trabajador

- El panel muestra el nombre visible del negocio.
- Muestra la sucursal activa y el nombre del trabajador.
- Aplica logo y colores personalizados del negocio.

### Actualización 046.1

- Catálogo único de módulos válidos (`/api/modules/catalog`).
- La configuración normaliza automáticamente módulos antiguos o desconocidos.
- Los módulos omitidos por paneles anteriores conservan su valor predeterminado.
- Se evita que el mismo módulo tenga que habilitarse desde lugares diferentes.

## Abrir sin consola negra

1. La primera vez, ejecute `INSTALAR_WINDOWS.bat`.
2. Después abra `ABRIR_NEGROSKY_CONTROL.vbs`.
3. En el panel gráfico pulse **Iniciar**.

El panel muestra el estado, la versión, los errores y las URL para administrador, trabajador y cliente, tanto para PC como para celular. También permite iniciar, detener, reiniciar, abrir la plataforma y crear respaldos.

Como alternativa se conserva `INICIAR_NEGROSKY.bat`. Para detener desde un acceso directo también puede usar `DETENER_NEGROSKY.bat`.

## Actualizar sin reinstalar ni perder datos

Extraiga esta carpeta junto a la versión anterior y abra `INICIAR_NEGROSKY.bat` una vez. Si todavía no existe `venv`, el iniciador reutiliza automáticamente la instalación y copia `data/negrosky_v2.db` desde la versión anterior. Después puede usar siempre el control gráfico.

Al actualizar, use el `INICIAR_NEGROSKY.bat` de esta carpeta nueva. El Control BUILD 055 también muestra si la dirección está atendida por BUILD 055 o por una versión antigua; al pulsar **Iniciar** reemplaza únicamente un servidor NEGROSKY anterior.

También puede copiar manualmente `data/negrosky_v2.db` y la carpeta `backups` antes de reemplazar una instalación. BUILD 025 conserva la migración automática y mantiene negocios, diseños, logos, sucursales, clientes, progresos, premios, citas e historial.

## Acceso inicial

- Usuario: `admin`
- Correo alternativo: `admin@negrosky.local`
- Contraseña: `ChangeMe123!`
- Administración PC: `http://127.0.0.1:8030`
- Trabajador PC: `http://127.0.0.1:8030/worker`

Cambie la contraseña antes de publicar. El celular debe estar en la misma red Wi-Fi y Windows debe permitir el acceso en redes privadas. Las URL móviles exactas aparecen dentro del panel administrativo y del Control Center.

## Permisos importantes

- Administrador general: crea y administra negocios, administradores generales y respaldos.
- Dueño/administrador del negocio: administra únicamente su negocio y puede crear sucursales; no puede crear otros negocios.
- Administrador de sucursal: opera dentro de su sucursal según los permisos disponibles.
- Trabajador: solo usa el panel de trabajador, valida compras/premios y puede registrar un cliente asistido; no puede crear negocios ni sucursales.

Estas restricciones se verifican en la interfaz y nuevamente en el servidor.

## Funciones terminadas hasta BUILD 025

- URL detectada automáticamente según el dispositivo desde donde se abre la plataforma.
- Una sección de URL por cada negocio, con su nombre y enlaces separados para PC y celular.
- Negocios, sucursales y clientes ordenados; aislamiento comprobado para impedir que un dueño consulte otro negocio.
- Agenda de citas activable por negocio o sucursal, con servicios, duración, precio, disponibilidad y control de estados.
- Calendario del cliente con días con cupos disponibles y horas libres en formato de 12 horas. Cuando un día se agota, propone la siguiente fecha.
- El cliente puede cancelar una cita futura con un motivo; la disponibilidad se libera inmediatamente y el dueño puede consultar la razón.
- Calendario mensual privado para el dueño, con la agenda del día, clientes, sucursales, duración aproximada y estado en español.
- Trabajador y dueño pueden registrar una demora estimada; se bloquean nuevos horarios que se cruzarían y se avisa de posibles citas afectadas sin mover las existentes.
- Horarios de apertura y cierre se escogen en formato de 12 horas (a. m. y p. m.).
- Notificaciones internas de compras, premios y nuevas citas cuando el módulo está activado; barra inferior que aparece en segundos y se oculta sola.

- Inicio por usuario o correo opcional, sesiones recordadas por un año y cierre de sesiones remotas.
- Bloqueo temporal tras cinco intentos incorrectos, cambio obligatorio de contraseña temporal y recuperación con código de soporte.
- Administradores generales adicionales, bloqueo/reactivación de usuarios y soporte de cuentas.
- Borrado seguro de trabajadores por el dueño: se cierra el acceso sin eliminar sus ventas ni movimientos históricos.
- URL de PC y celular para administración, trabajador y cliente.
- QR con URL de red local para abrir la vista móvil del trabajador, código manual de seis números y renovación automática al vencer.
- Horarios por negocio/sucursal, apagado manual y zona `America/Bogota` compatible con Windows.
- Módulos activables por negocio o sucursal; desactivar fidelización o página pública se hace cumplir en el servidor.
- Campañas editables, pausables, reanudables y papelera sin borrar progresos.
- Cantidad de premios oculta, ilimitada o visible; bloqueo formal cuando se agotan.
- Reclamo agrupado de varios premios y teclado numérico integrado para el trabajador.
- Registro asistido de clientes, origen/sucursal, búsqueda sin distinguir mayúsculas ni tildes, ficha completa, notas, etiquetas y unión de duplicados.
- Exportación CSV de clientes, compras y premios.
- Historial privado del negocio con fecha, cliente, campaña, sucursal y trabajador que validó cada movimiento.
- Papelera de negocios y sucursales con respaldo automático.
- Respaldos completos, descarga, restauración, diagnóstico y reinicio general protegido.
- Panel adaptable para computador y celular.
- Diseñador visual independiente por negocio con logo, nombre visible, mensaje de bienvenida, colores, fondo, botones, estilos de tarjeta y vista previa en vivo.
- Logos PNG, JPG o WebP de máximo 2 MB guardados dentro de la base de datos para incluirlos en los respaldos.
- Aplicación automática del diseño en la página pública del cliente para PC, Android y iPhone mediante navegador.

## Pruebas

```bat
venv\Scripts\python.exe -m pytest -q
```

El paquete se entrega con 14 pruebas automatizadas del backend, seguridad, aislamiento entre negocios, permisos, QR, horarios, búsquedas, citas, cancelaciones, demoras, calendario, notificaciones, respaldos y flujo completo de fidelización.

## Aún pendiente para futuras versiones

- Notificaciones externas por WhatsApp, correo o push.
- Ocho negocios de demostración con temáticas diferentes.
- Idiomas, países, monedas y zonas horarias adicionales.
- Publicación en servidor con HTTPS para cámara y acceso externo.

La arquitectura conserva como regla que los módulos nuevos puedan activarse por negocio y, cuando corresponda, por sucursal.

## BUILD 024

En Diseño visual puedes escoger una campaña activa, ajustar compras de ejemplo y alternar entre vista de celular y escritorio. Se usa la misma plantilla de tarjeta que ve el cliente. Los datos de ejemplo no modifican compras ni premios reales. La base de datos incluida conserva los datos del BUILD 023. El entorno `venv` de Windows se vuelve a instalar mediante `INSTALAR_WINDOWS.bat`.

## BUILD 025

Se corrigió la interrupción del código del panel que impedía cargar los campos de Diseño visual en BUILD 024. Se confirmó la carga de campañas y logos y que el diseño se guarda y vuelve a mostrarse después de actualizar la página. El mensaje de guardado permanece visible.

## BUILD 026

El color secundario ahora tiñe el fondo de la página pública y los sellos completados; la barra de progreso usa los colores principal y secundario en la vista previa y en la tarjeta del cliente. Los estilos CSS se cargan con versión para evitar que el navegador conserve los anteriores. Las compras de ejemplo de la vista previa son independientes del progreso real de cada cliente.

## BUILD 027

El diseñador incluye temas adaptables para restaurantes, cafeterías, belleza, mascotas, salud, gimnasio, comercio, piscinas y negocios premium. Sugiere un tema según el nombre del negocio y permite modificar colores, fondo, tipografía, formas, transparencia, sellos, barra de progreso, texto del botón y secciones visibles. También admite imagen de fondo y restauración del diseño original. La vista previa usa una campaña real y los mismos estilos de la página pública.

## BUILD 028

El diseñador permite configurar teléfono, WhatsApp, dirección, Instagram, Facebook, TikTok, sitio web y Google Maps por negocio. Los botones se muestran en la página pública y usan los colores y la forma del tema. El horario público se toma automáticamente de “Horarios y módulos”, puede ocultarse de manera independiente y se actualiza sin duplicar configuraciones. La imagen de fondo admite encuadres iguales o independientes para celular y escritorio, con ajuste de tamaño y posición horizontal y vertical, opacidad de foto y oscurecimiento de lectura. El logo tiene tamaño, opacidad, color de fondo, forma y ajuste de imagen configurables. Cada campaña puede heredar, mostrar siempre u ocultar título, sellos, barra, premio y botón, con prioridad sobre el diseño general.

## BUILD 029

Las redes sociales se muestran como módulos compactos: solo logo, solo texto o ambos. Se puede escoger tamaño, ubicación interna o flotante, esquina y visibilidad independiente en celular y PC. El diseñador permite ordenar contacto, perfil, campañas, premios y citas de manera distinta para móvil y escritorio. La página pública usa iconos ligeros integrados y conserva los enlaces seguros configurados en BUILD 028.

## BUILD 030

La página pública usa una distribución amplia en escritorio y conserva una lectura vertical en celular. La vista previa del panel tiene desplazamiento propio para que permanezca utilizable durante diseños extensos. Los módulos se seleccionan con clic, se arrastran para ordenar y permiten ajustar su ancho para móvil y PC de forma independiente. Los iconos de redes se reemplazaron por vectores reconocibles.
