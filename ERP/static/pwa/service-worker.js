self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('lpg-cache-v1').then(cache => {
      return cache.addAll([
        '/',
        '/static/pwa/manifest.json'
      ]);
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
