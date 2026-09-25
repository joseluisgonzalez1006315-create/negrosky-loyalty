(() => {
  const stack = document.createElement('div');
  stack.className = 'toast-stack';
  stack.setAttribute('role', 'status');
  stack.setAttribute('aria-live', 'polite');
  document.body.append(stack);
  window.showToast = (message, kind = 'info', imageUrl = '') => {
    const entry = document.createElement('div');
    entry.className = `bottom-toast ${['success', 'error'].includes(kind) ? kind : 'info'}`;
    if (imageUrl) { const image = document.createElement('img'); image.className = 'toast-image'; image.src = imageUrl; image.alt = ''; entry.append(image); }
    const text = document.createElement('div'); text.textContent = String(message || 'Notificación'); entry.append(text);
    stack.append(entry);
    while (stack.children.length > 3) stack.firstElementChild.remove();
    setTimeout(() => { entry.classList.add('leaving'); setTimeout(() => entry.remove(), 300); }, 5200);
  };
})();
