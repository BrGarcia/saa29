// SAA29 Service Worker para PWA Mobile
const CACHE_NAME = 'saa29-mobile-v3';
const ASSETS_TO_CACHE = [
  '/static/css/index.css',
  '/static/css/mobile.css',
  '/static/js/app.js',
  '/static/js/mobile/app_mobile.js',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
      // Sem isto, um SW novo instalado fica "waiting" até todas as abas
      // controladas pelo antigo fecharem — a home de um app de pátio fica
      // aberta o dia todo, então uma troca de CSS/JS nunca chegava a
      // aparecer sem o usuário limpar dados do site manualmente. Achado
      // real: precache de mobile.css continuou servindo classes antigas
      // (.mobile-stats/.mobile-filter-pill inexistentes) mesmo depois do
      // arquivo já ter sido reescrito no servidor.
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key.startsWith('saa29-mobile-') && key !== CACHE_NAME)
        .map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const isStaticAsset = request.method === 'GET' && url.origin === self.location.origin && (
    url.pathname.startsWith('/static/') || url.pathname === '/manifest.json'
  );

  if (!isStaticAsset) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.match(request).then((cachedResponse) => cachedResponse || fetch(request))
  );
});
