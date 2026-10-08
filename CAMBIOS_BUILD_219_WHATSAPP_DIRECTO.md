# Build 219 · WhatsApp directo al negocio

- El número del negocio se normaliza a formato internacional colombiano (+57) aunque esté guardado con espacios, 0 inicial o 00.
- El enlace del cliente usa la API directa de WhatsApp con el número del negocio.
- En celulares intenta abrir la aplicación con el destinatario ya definido y solo usa el enlace web como respaldo si la aplicación no está instalada.
- Se conserva el mensaje personalizado y la información de la cita.
