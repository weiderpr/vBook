self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: data.icon || '/book/static/images/hero.png',
            badge: data.badge || '/book/static/images/hero.png',
            data: data.data,
            vibrate: [100, 50, 100],
            actions: [
                { action: 'open', title: 'Ver agora' }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    let url = '/book/mobile/home/';
    if (event.notification.data && event.notification.data.url) {
        url = event.notification.data.url;
    }

    event.waitUntil(
        clients.openWindow(url)
    );
});

// Cache básico para PWA
const CACHE_NAME = 'vbook-cache-v1';
const ASSETS = [
    '/book/mobile/home/',
    '/book/static/css/style_v3.css',
    '/book/static/manifest.json'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
    );
});

self.addEventListener('fetch', event => {
    // Estratégia: Network First, falling back to cache
    if (event.request.method === 'GET') {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(event.request))
        );
    }
});
