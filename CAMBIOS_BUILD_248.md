# Build 248 · módulos y estadísticas cargan

## Causa encontrada
El navegador estaba deteniendo `web/app.js` antes de ejecutar la carga de módulos. El listener del editor visual usaba `previewSurface` sin declararlo; el error `ReferenceError: previewSurface is not defined` impedía que se registraran la sesión, los módulos y Estadísticas.

## Cambios
- Declaración segura de `previewSurface` y listener solo cuando existe el elemento.
- Versionado de backend, indicador visible y `VERSION.txt` a 3.0.248 / Build 248.
- Cache busting de CSS, JavaScript y Service Worker a v248 para no reutilizar el frontend anterior.

## Validación
- `node --check web/app.js`
- `python3 -m py_compile app/main.py main.py`
- Se verificó que solo queda el listener protegido y que los scripts locales apuntan a v248.
