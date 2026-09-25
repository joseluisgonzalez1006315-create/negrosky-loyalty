# Pruebas BUILD 024

- `python -m pytest -q tests/test_foundation.py`: 17 pruebas correctas, incluida la migración de una base sin `business_branding`, guardado y consulta pública del diseño.
- `node --check` en app, customer y renderizador compartido: sintaxis correcta.
- Prueba del renderizador con siete sellos, tres compras de ejemplo, imagen del sello, barra al 43 % y acción desactivada en la vista previa.
- Comparación SQLite de la base de datos copiada con BUILD 023: mismos datos y respaldos.
- Pendiente de comprobar de forma presencial: apariencia en navegadores de Windows, Android e iPhone y accesibilidad por Wi-Fi real.
