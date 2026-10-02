// La misma tarjeta se usa en la página del cliente y en el diseñador visual.
window.NegroskyCard = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function render(c, {preview = false} = {}) {
    const target = Math.max(1, Math.min(100, Number(c.target_purchases) || 1));
    const progress = Math.max(0, Math.min(target, Number(c.progress) || 0));
    const exhausted = c.reward_stock !== null && c.reward_stock !== undefined && Number(c.rewards_remaining) === 0;
    const percent = Math.round(progress / target * 100);
    const remaining = target - progress;
    const icon = c.icon_url ? `<img class="stamp-icon" src="${escape(c.icon_url)}" alt="">` : escape(c.progress_emoji || '⭐');
    const stamps = Array.from({length: target}, (_, i) => `<span class="stamp ${i < progress ? 'done' : ''}">${icon}</span>`).join('');
    let availability = '';
    if (exhausted) availability = '<div class="exhausted-card"><div>⛔</div><h3>Premios agotados</h3><p>Agradecemos tu interés. Esta campaña ha entregado todos los premios disponibles.</p></div>';
    else if (c.reward_display === 'unlimited') availability = '<p class="reward-availability">🎁 Premios ilimitados</p>';
    else if (c.reward_display === 'quantity') availability = `<p class="reward-availability">🎁 Quedan <b>${Number(c.rewards_remaining)}</b> de ${Number(c.reward_stock)} premios</p>`;
    const action = exhausted ? 'Premios agotados' : remaining ? (c.button_label || 'Registrar mi compra') : 'Registrar otra compra';
    const id = Number(c.program_id || c.id);
    const visible = key => c[key] !== false;
    const heading = visible('show_title') ? `<div class="card-heading"><p class="eyebrow">${escape(c.program_name || c.name)}</p>${visible('show_progress') ? `<span class="progress-percent">${percent}%</span>` : ''}</div>` : '';
    const stampBlock = visible('show_stamps') ? `<div class="stamp-track">${stamps}</div>` : '';
    const progressBlock = visible('show_progress') ? `<div class="progress-caption"><b>${progress} de ${target}</b><span>${remaining ? `Faltan ${remaining} compra${remaining === 1 ? '' : 's'}` : '¡Meta completada!'}</span></div><div class="progress"><i style="width:${percent}%"></i></div>` : '';
    const rewardBlock = visible('show_reward') ? `<p class="reward-line">🎁 Premio: <b>${escape(c.reward_name)}</b></p>${availability}` : '';
    const button = visible('show_button') ? `<button class="full" ${preview || exhausted ? 'disabled' : ''} ${preview ? '' : `onclick="purchase(${id})"`}>${action}</button>` : '';
    return `<div class="loyalty-card ${exhausted ? 'card-exhausted' : ''}">${heading}${stampBlock}${progressBlock}${rewardBlock}${button}</div>`;
  }
  return {render};
})();
