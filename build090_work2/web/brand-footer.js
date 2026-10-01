(function(){
  const style=document.createElement('style');
  style.textContent='.negrosky-brand-footer{width:100%;box-sizing:border-box;display:flex;align-items:center;justify-content:center;gap:7px;flex-wrap:wrap;padding:18px 12px 22px;margin-top:24px;color:#aaa3bb;font:600 12px/1.3 Arial,sans-serif;text-align:center;letter-spacing:.1px}.negrosky-brand-footer small{width:100%;color:#777083;font-size:10px;font-weight:400}.negrosky-footer-check{display:inline-grid;place-items:center;width:17px;height:17px;border-radius:50%;background:#7c3aed;color:#fff;font-size:11px;font-weight:900}';
  document.head.appendChild(style);
  if(document.querySelector('.negrosky-brand-footer')) return;
  const footer=document.createElement('footer');
  footer.className='negrosky-brand-footer';
  footer.innerHTML='<span class="negrosky-footer-check">✓</span><span>Creado y verificado por <b>NEGROSKY</b></span><small>Plataforma de fidelización para negocios</small>';
  document.body.appendChild(footer);
})();
