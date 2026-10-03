# Build 188 · Corrección de papelera y borrado de clientes

- Se agrega la migración automática de `customers.deleted_at` para PostgreSQL/Supabase.
- Se corrige el envío de clientes a papelera.
- El administrador general ve también “Eliminar definitivamente” desde la lista activa y desde la papelera.
- El negocio solo puede enviar a papelera y restaurar.
- El borrado definitivo sigue protegido para el administrador general y crea respaldo.
