// SAA29 Service Worker para PWA Mobile
const CACHE_NAME = 'saa29-mobile-v1';
const ASSETS_TO_CACHE = [
  '/m/',
  '/static/css/index.css',
  '/static/css/mobile.css',
  '/static/js/app.js',
  '/static/js/mobile/app_mobile.js',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      return cachedResponse || fetch(event.request);
    })
  );
});
