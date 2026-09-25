# CAMBIOS · BUILD 013 DEMO

## Incluido en esta actualización

- Horario semanal editable para cada negocio.
- Horario propio por sucursal o herencia del horario general.
- Apertura y cierre manual sin fecha límite.
- Mensaje formal “Fuera de servicio” visible para el cliente.
- Bloqueo real en el servidor: mientras esté cerrado no se crean ni autorizan compras o premios.
- Zona horaria configurable; viene preparada para `America/Bogota`.
- Duplicación de horarios y módulos a una o varias sucursales.
- El cierre manual no se duplica por seguridad.
- Configuración por negocio o sucursal para fidelización, página pública, citas, venta de tiempo y notificaciones.
- QR con enlace completo al panel del trabajador y código temporal de 6 números.
- Si el trabajador ya inició sesión, el QR abre directamente la verificación.
- Si no inició sesión, el código se conserva mientras ingresa.
- Vista previa con nombre, celular, campaña, premio y cantidad antes de autorizar.
- Código manual y teclado numérico interno conservados.
- Migración automática de la base de datos sin borrar clientes, progreso, premios ni historial.
- Diseño responsive reforzado en horarios y verificación móvil.
- Creación de negocios corregida: la URL se genera desde el nombre y acepta texto, acentos o una URL completa.
- Ejemplo y vista previa de la dirección pública antes de crear el negocio.
- Mensajes de error legibles cuando la URL ya existe o algún dato no es válido.
- Aviso visual formal para clientes cuando no hay campañas activas.
- Buscador administrativo de clientes por nombre o celular.
- Ficha completa del cliente con sucursal de origen, consentimiento, campañas, progreso, ciclos, premios e historial.

## Preparado, pero aún pendiente de completar

- Recuperación de usuario/contraseña por el propio usuario.
- Inicio por nombre de usuario o correo opcional.
- Códigos temporales de soporte y más administradores generales.
- Alta de clientes sin internet desde el panel del trabajador.
- Módulo completo de citas.
- Módulo completo de venta por tiempo.
- Notificaciones de compra.
- Diseñador visual, plantillas por tipo de negocio y previsualización.
- Ocho negocios de demostración con campañas, temas y datos.
- Panel gráfico para iniciar, detener y reiniciar el servidor.
- Copias de seguridad visibles, restauración, borrado de negocios/sucursales y reinicio general.
- Catálogo universal de tipos de negocio.

## Actualización sin reinstalar

El iniciador reutiliza los componentes instalados de otra carpeta BUILD. Para conservar una base concreta al cambiar manualmente de carpeta, copia `data/negrosky_v2.db` antes de iniciar la nueva versión. No reemplaces una base con otra después de haber trabajado en ambas, porque cada una puede contener movimientos diferentes.

## URLs estables

- Administrador en el PC: `http://127.0.0.1:8030`
- Trabajador en el PC: `http://127.0.0.1:8030/worker`
- Cliente de demostración: `http://127.0.0.1:8030/b/santuario`
- En celular se usa la IP Wi-Fi que muestra el iniciador, siempre en el puerto `8030`.
