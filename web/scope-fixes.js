// BUILD 056 scope rules: roulette is retired from Negrosky Loyalty.
(function(){
  const hide=()=>{
    document.querySelectorAll('[data-view=\"roulette\"],#view-roulette,[data-module-admin=\"roulette\"],#roulette-form,#roulette-list,#customer-roulette').forEach(el=>{el.classList.add('hidden');el.setAttribute('aria-hidden','true')});
  };
  hide();
  new MutationObserver(hide).observe(document.body,{childList:true,subtree:true});
  if(location.pathname.startsWith('/b/')) window.loadCustomerRoulette=async()=>{};
})();
