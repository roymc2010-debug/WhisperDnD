// Service Worker para WhisperDnD & Study PWA
importScripts('/static/vendor/precache.js');
const CACHE_NAME = 'whisper-desktop-redesign-1';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/static/manifest.json',
  ...self.DESKTOP_ASSETS,
  '/static/styles.css',
  '/static/desktop.css',
  '/static/js/desktop-core.js',
  '/static/js/desktop.js',
  '/static/js/utils.js',
  '/static/js/api.js',
  '/static/js/progress.js',
  '/static/js/audio.js',
  '/static/js/drive.js',
  '/static/js/roster.js',
  '/static/js/wiki.js',
  '/static/js/notes.js',
  '/static/js/app.js',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('Fallo al pre-cachear algunos assets durante la instalación del SW:', err);
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Omitir endpoints API, streaming de audio o peticiones que no sean GET
  if (url.pathname.startsWith('/api/') || event.request.method !== 'GET') {
    return;
  }

  // Estrategia Network-First con fallback a Caché para archivos locales (.js, .css, .html)
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          if (event.request.mode === 'navigate') {
            return caches.match('/');
          }
        });
      })
  );
});
