# CAMBIOS · BUILD 017 DEMO

## Terminado

- Interfaz de citas en español: estados «Programada», «Confirmada», «Completada», «Cancelada» y «No asistió» para cliente y dueño. Se tradujeron también estados de cuentas y negocios visibles.
- Horas visibles en formato de 12 horas con a. m. y p. m. en calendario, selección de citas, agenda del trabajador y edición de horarios. Los valores internos siguen guardándose en formato estándar.
- Calendario del cliente por servicio y sucursal. Solo se pueden seleccionar los días con cupos. Al elegir uno, se muestran únicamente las horas disponibles.
- Cancelación por el cliente de una cita futura con un motivo obligatorio. Queda registrada la razón, se libera el horario y el dueño la puede consultar. Cada cliente solo puede cancelar sus propias citas.
- Calendario mensual para el dueño y administradores autorizados. Filtra por negocio y sucursal, muestra las citas de cada día con nombre, teléfono, servicio, duración aproximada y estado, y permite cambiar su estado.
- Dueño o trabajador de la sucursal puede informar una demora de 0 a 180 minutos. Se muestra la finalización estimada, se bloquean nuevas reservas que se cruzarían con la demora y se señala cuántas citas existentes podrían verse afectadas. Las citas ya reservadas conservan sus horas. Con el módulo de notificaciones activo, se avisa a clientes afectados.
- Migración automática de los datos de citas de BUILD 016 sin borrar reservas anteriores.

## Comprobado

- 14 pruebas automatizadas: calendario, fechas y horas disponibles, cancelación propia y rechazo de cuentas ajenas, horario liberado, demora y permisos por negocio/sucursal, junto a los flujos anteriores.
- Sintaxis Python y JavaScript verificada. Las pruebas no sustituyen una prueba física de Safari o Android en el teléfono.

## Pendiente

- Mover manualmente o reprogramar citas afectadas por demoras desde la agenda; ninguna cita se desplaza de forma automática.
- Venta y control de tiempo para negocios que venden minutos u horas.
- Diseñador visual con plantillas, imágenes y previsualización.
- Notificaciones externas por WhatsApp, correo o push; los avisos internos se ven con la página abierta y el módulo habilitado.
- Ocho negocios de demostración completos, más idiomas, países, monedas y publicación con HTTPS.
