# Respaldo completo V93

Esta versión corrige el flujo de copias de seguridad y restauración.

- El respaldo `.zip` contiene la base de datos completa.
- Las imágenes guardadas como datos dentro de la base se conservan con la base de datos.
- También se incluyen los archivos externos encontrados en `storage`, `uploads`, `media`, `assets`, `resources` y `files`.
- El manifiesto del ZIP registra los archivos externos realmente incluidos.
- Al restaurar un ZIP, se valida el manifiesto, se recupera la base de datos y se restauran los archivos externos.
- La instalación desde archivo acepta tanto `.db` como `.zip`.

Para instalar una copia: abre **Respaldos y sistema**, elige **Instalar copia desde archivo**, selecciona el ZIP y confirma la restauración.
