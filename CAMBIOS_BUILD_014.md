# CAMBIOS · BUILD 014 DEMO

## Terminado y comprobado

- Cuentas por usuario o correo opcional, contraseña temporal obligatoria, bloqueo por intentos y recuperación con código.
- Sesiones persistentes, listado y revocación desde Seguridad.
- Administradores generales adicionales y soporte de usuarios.
- El dueño no puede crear negocios: únicamente sucursales dentro de su negocio.
- El trabajador no puede crear negocios ni sucursales y es enviado a su panel operativo.
- El dueño puede borrar trabajadores de su negocio sin borrar sus ventas; el historial conserva quién realizó cada movimiento.
- URL para PC y celular mostradas en Administración y Control Center.
- Corrección del QR de compra: imagen, enlace directo y código de seis números.
- Corrección de zona horaria `America/Bogota` incluso si Windows no tiene la base IANA instalada.
- Búsqueda de clientes sin distinguir mayúsculas, minúsculas o tildes.
- Registro asistido, notas, etiquetas, ficha, exportaciones y unión de duplicados.
- Papelera para negocios/sucursales y respaldos antes de operaciones delicadas.
- Respaldos descargables/restaurables, diagnóstico y reinicio general protegido.
- Control gráfico para iniciar, detener y reiniciar sin dejar una consola visible.
- Activación real del módulo de fidelización y de la página pública por negocio/sucursal.

## Verificación realizada

- 8 pruebas automatizadas aprobadas.
- Flujo completo: cliente → QR/código → vista previa → autorización → progreso → premio.
- Restricciones de administrador general, dueño y trabajador.
- Bloqueo tras cinco intentos, recuperación, sesiones, horarios, QR, búsqueda, exportación y respaldo.
- Sintaxis Python y JavaScript y arranque real del servidor.

## Pendiente

- Citas, notificaciones, venta de tiempo, diseñador avanzado, negocios demo e internacionalización.
