const CACHE='negrosky-shell-v1';
self.addEventListener('install',event=>{self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim())});
self.addEventListener('push',event=>{let data={title:'NEGROSKY',body:'Tienes una nueva notificación',url:'/'};try{data={...data,...(event.data?.json()||{})}}catch(e){}event.waitUntil(self.registration.showNotification(data.title,{body:data.body,icon:'/static/pwa-icon.svg',badge:'/static/pwa-icon.svg',data:{url:data.url||'/'},vibrate:[100,50,100]}))});
self.addEventListener('notificationclick',event=>{event.notification.close();const url=event.notification.data?.url||'/';event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{const open=list.find(client=>client.url.includes(url));return open?open.focus():clients.openWindow(url)}))});
