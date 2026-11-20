// Red primero, caché si no hay internet (la app abre offline; la radio sí necesita internet).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const url = e.request.url;
  if (e.request.method !== 'GET' || !url.startsWith(self.location.origin)) return;
  e.respondWith(fetch(e.request).then(r => {
    const copy = r.clone(); caches.open('mochi-v3').then(c => c.put(e.request, copy)); return r;
  }).catch(() => caches.match(e.request)));
});
