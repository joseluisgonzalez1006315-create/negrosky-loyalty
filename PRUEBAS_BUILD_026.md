# Pruebas BUILD 026

- API de diseño guardada con colores primario, secundario, botón y fondo.
- Página pública cargada contra un servidor temporal: nombre del negocio, clase de tema, variables de color y versión del CSS comprobados.
- Reglas para fondo, sellos completados y barra de progreso presentes en la página pública.
- `python -m pytest -q tests/test_foundation.py`: 17 pruebas correctas.
- `node --check` de app.js, customer.js y loyalty-card.js: sintaxis correcta.
- El progreso mostrado en el diseñador es simulado; el del cliente procede de sus compras.
- Pendiente: inspección visual en Chrome de Windows y navegadores Android/iPhone reales.
