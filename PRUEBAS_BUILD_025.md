# Pruebas BUILD 025

- Carga real del panel contra el servidor y una base temporal con Santuario Granizados y una campaña de siete sellos: nombre, bienvenida, campaña y tarjeta visibles.
- Edición de nombre, bienvenida y color: la vista previa se actualiza al escribir.
- Guardado y recarga: los tres valores continúan en la API pública y reaparecen tras volver a abrir la página.
- Ningún error de ejecución del script en el entorno DOM de prueba.
- `python -m pytest -q tests/test_foundation.py`: 17 pruebas correctas.
- `node --check` de los archivos JS: sintaxis correcta.
- La base de datos incluida es idéntica a la del BUILD 024 recibido y los respaldos permanecen.
- Queda por probar visualmente en Windows, Android e iPhone reales.
