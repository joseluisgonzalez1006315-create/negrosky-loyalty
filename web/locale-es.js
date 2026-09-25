(() => {
  const appointmentStates = {
    scheduled: 'Programada', confirmed: 'Confirmada', completed: 'Completada',
    cancelled: 'Cancelada', no_show: 'No asistió',
  };
  const states = {
    ...appointmentStates, active: 'Activo', inactive: 'Inactivo',
    trashed: 'En la papelera', blocked: 'Bloqueado', deleted: 'Eliminado',
    available: 'Disponible', used: 'Utilizado', pending: 'Pendiente', expired: 'Vencido',
  };
  const two = value => String(value).padStart(2, '0');
  function clock(time) {
    const [hour, minute] = String(time).split(':').map(Number);
    if (!Number.isInteger(hour) || !Number.isInteger(minute)) return time;
    return `${hour % 12 || 12}:${two(minute)} ${hour < 12 ? 'a. m.' : 'p. m.'}`;
  }
  function dateTime(value, timeZone) {
    try {
      return new Intl.DateTimeFormat('es-CO', {
        timeZone: timeZone || 'America/Bogota', dateStyle: 'medium',
        timeStyle: 'short', hour12: true,
      }).format(new Date(value));
    } catch {
      return new Intl.DateTimeFormat('es-CO', {timeZone: 'America/Bogota',
        dateStyle: 'medium',timeStyle: 'short',hour12: true}).format(new Date(value));
    }
  }
  function dayKey(value, timeZone) {
    let fields;
    try { fields = new Intl.DateTimeFormat('en-US', {
      timeZone: timeZone || 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date(value)); }
    catch { fields = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date(value)); }
    const part = type => fields.find(field => field.type === type)?.value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }
  function appointmentTime(value, timeZone) {
    try { return new Intl.DateTimeFormat('es-CO', {
      timeZone: timeZone || 'America/Bogota', hour: 'numeric', minute: '2-digit', hour12: true,
    }).format(new Date(value)); }
    catch { return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota', hour: 'numeric', minute: '2-digit', hour12: true,
    }).format(new Date(value)); }
  }
  function escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }
  function delayForm(id, current = 0) {
    return `<details class="delay-box"><summary>Informar una demora</summary><form class="delay-form" data-delay-id="${id}">
      <label>Minutos de demora estimados<input name="minutes" type="number" min="0" max="180" value="${current}" required></label>
      <label>Motivo (opcional)<input name="reason" maxlength="250" placeholder="Ejemplo: la atención se prolongó"></label>
      <small>Escribe 0 para quitar la demora. Las citas posteriores no cambian de hora automáticamente.</small>
      <button type="submit">Actualizar demora</button></form></details>`;
  }
  window.NegroskyES = { appointmentStates, states, clock, dateTime, dayKey,
    appointmentTime, escape, delayForm };
})();
