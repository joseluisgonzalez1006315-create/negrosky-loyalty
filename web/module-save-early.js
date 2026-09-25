(() => {
  const form = document.getElementById('module-form');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();

    const select = document.getElementById('module-tenant');
    const message = document.getElementById('module-message');
    const button = form.querySelector('button[type="submit"], button:not([type])');
    const token = localStorage.getItem('negrosky_token');
    const tenantId = Number(select?.value || 0);
    const modules = {};
    form.querySelectorAll('[data-module-admin]').forEach((input) => {
      modules[input.dataset.moduleAdmin] = Boolean(input.checked);
    });

    if (!tenantId) {
      if (message) message.textContent = 'Selecciona un negocio antes de guardar.';
      return;
    }

    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/tenant-modules', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ tenant_id: tenantId, modules }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `No se pudo guardar (${response.status})`);
      const saved = data.modules || modules;
      form.querySelectorAll('[data-module-admin]').forEach((input) => {
        input.checked = Boolean(saved[input.dataset.moduleAdmin]);
      });
      const summary = document.getElementById('module-summary');
      if (summary) {
        summary.innerHTML = [...form.querySelectorAll('[data-module-admin]')].map((input) => {
          const label = input.closest('.module-admin-card')?.querySelector('b')?.textContent || input.dataset.moduleAdmin;
          const active = Boolean(saved[input.dataset.moduleAdmin]);
          return `<div class="module-summary-row"><span>${label}</span><b class="${active ? 'module-on' : 'module-off'}">${active ? 'ACTIVO' : 'OCULTO'}</b></div>`;
        }).join('');
      }
      if (message) message.textContent = 'Funciones guardadas correctamente para este negocio.';
      if (window.showToast) window.showToast('Funciones guardadas correctamente', 'success');
      document.dispatchEvent(new CustomEvent('tenant-modules-saved', { detail: { tenantId, modules: saved } }));
    } catch (error) {
      if (message) message.textContent = `Error al guardar: ${error.message}`;
      if (window.showToast) window.showToast(error.message, 'error');
    } finally {
      if (button) button.disabled = false;
    }
  }, true);
})();
