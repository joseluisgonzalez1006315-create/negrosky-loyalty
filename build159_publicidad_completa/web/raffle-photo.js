/* BUILD 055: photo upload for raffle prize, encoded in the existing image_url field. */
(function(){
  function wire(){
    const form=document.getElementById('raffle-form');
    const old=document.getElementById('raffle-image');
    if(!form||!old||old.dataset.photoReady)return;
    old.dataset.photoReady='1';
    old.type='file'; old.accept='image/*'; old.id='raffle-image-file'; old.name='raffle-image-file';
    old.insertAdjacentHTML('afterend','<input type="hidden" id="raffle-image" name="image_url"><small id="raffle-image-preview" class="muted">Puedes seleccionar una foto del producto.</small>');
    const hidden=document.getElementById('raffle-image'), preview=document.getElementById('raffle-image-preview');
    old.addEventListener('change',()=>{const file=old.files&&old.files[0];if(!file){hidden.value='';preview.textContent='Puedes seleccionar una foto del producto.';return}if(file.size>4*1024*1024){old.value='';hidden.value='';preview.textContent='La imagen debe pesar máximo 4 MB.';return}const reader=new FileReader();reader.onload=()=>{hidden.value=reader.result;preview.textContent='Foto seleccionada: '+file.name};reader.readAsDataURL(file)});
  }
  const observer=new MutationObserver(wire); observer.observe(document.documentElement,{childList:true,subtree:true}); setTimeout(wire,500);
})();
