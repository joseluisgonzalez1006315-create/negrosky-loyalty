# Build 250 · pulido visual del panel administrativo

Esta versión continúa el rediseño visual sobre Build 249, que ya corrigió la sincronización de las casillas de módulos.

## Cambios

- Encabezado y navegación del panel con jerarquía visual más clara, estados activos consistentes y mejor lectura en PC y celular.
- Tarjetas del resumen con mejor contraste, separación y respuesta visual.
- Tarjetas de “Módulos por negocio” con estado visual inmediato: activo en verde y oculto en estado neutro/rojo.
- El estado visual de cada módulo se actualiza al marcar o desmarcar sin alterar el guardado existente.
- Se mantuvo intacta la lógica de permisos, API, citas, reservas, rifas, fidelización, publicidad y base de datos.
- Cache busting actualizado a v250.

## Validación

- `node --check web/app.js`
- `python -m py_compile app/main.py main.py`
- Prueba manual prevista: abrir panel, entrar a Módulos por negocio, cambiar negocio, marcar/desmarcar y guardar.
