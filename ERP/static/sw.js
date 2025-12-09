// POS Service Worker for offline functionality
const CACHE_NAME = 'himalytix-pos-v1';
const STATIC_CACHE_NAME = 'himalytix-pos-static-v1';
const DYNAMIC_CACHE_NAME = 'himalytix-pos-dynamic-v1';

// Resources to cache for offline use
const STATIC_ASSETS = [
  '/',
  '/pos/',
  '/static/css/bootstrap.min.css',
  '/static/css/app.min.css',
  '/static/css/pos.css',
  '/static/libs/jquery/dist/jquery.min.js',
  '/static/libs/bootstrap/dist/js/bootstrap.bundle.min.js',
  '/static/js/app.js',
  '/static/libs/alpinejs.min.js',
  '/static/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png'
];

// API endpoints that should work offline (will be queued)
const API_ENDPOINTS = [
  '/pos/api/cart/add/',
  '/pos/api/cart/update/',
  '/pos/api/cart/remove/',
  '/pos/api/checkout/',
  '/pos/api/products/search/'
];

// Install event - cache static assets
self.addEventListener('install', event => {
  console.log('POS Service Worker installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then(async cache => {
        console.log('Caching static assets...');
        // Use Promise.allSettled so single missing asset doesn't break install
        const results = await Promise.allSettled(STATIC_ASSETS.map(async (url) => {
          try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`Request failed with status ${resp.status}`);
            await cache.put(url, resp.clone());
            return { url, status: 'cached' };
          } catch (err) {
            console.warn('Failed to cache', url, err);
            return { url, status: 'failed', error: err.message };
          }
        }));
        // Log summary
        results.forEach(r => {
          if (r.status === 'fulfilled') {
            // r.value contains result objects
            if (r.value && r.value.status === 'failed') {
              console.warn('Cache entry failed:', r.value.url, r.value.error);
            }
          }
        });
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('POS Service Worker activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== STATIC_CACHE_NAME && cacheName !== DYNAMIC_CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Handle API requests
  if (API_ENDPOINTS.some(endpoint => url.pathname.startsWith(endpoint))) {
    event.respondWith(handleApiRequest(event.request));
    return;
  }

  // Handle static assets
  if (STATIC_ASSETS.includes(url.pathname) || url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          return response || fetch(event.request);
        })
    );
    return;
  }

  // Handle navigation requests
  if (event.request.mode === 'navigate') {
    event.respondWith(
      caches.match('/pos/')
        .then(response => {
          return response || fetch(event.request);
        })
    );
    return;
  }

  // Default: try cache first, then network
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }

        return fetch(event.request)
          .then(response => {
            // Cache successful GET requests
            if (event.request.method === 'GET' && response.status === 200) {
              const responseClone = response.clone();
              caches.open(DYNAMIC_CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, responseClone);
                });
            }
            return response;
          })
          .catch(() => {
            // Return offline fallback for HTML pages
            if (event.request.headers.get('accept').includes('text/html')) {
              return caches.match('/pos/');
            }
          });
      })
  );
});

// Handle API requests with offline queuing
async function handleApiRequest(request) {
  try {
    // Try to make the request
    const response = await fetch(request);
    return response;
  } catch (error) {
    // If offline, queue the request
    console.log('API request failed, queuing for later:', request.url);

    // Store the request for later retry
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: null,
      timestamp: Date.now()
    };

    // Read request body if it exists
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      try {
        requestData.body = await request.clone().text();
      } catch (e) {
        console.warn('Could not read request body for queuing');
      }
    }

    // Store in IndexedDB
    await storeRequestForRetry(requestData);

    // Return a synthetic response indicating offline mode
    return new Response(
      JSON.stringify({
        success: false,
        offline: true,
        message: 'Request queued for when connection is restored',
        queued: true
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Store failed requests for retry when back online
async function storeRequestForRetry(requestData) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('pos-offline-queue', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction(['requests'], 'readwrite');
      const store = transaction.objectStore('requests');
      const addRequest = store.add(requestData);

      addRequest.onsuccess = () => resolve();
      addRequest.onerror = () => reject(addRequest.error);
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('requests')) {
        db.createObjectStore('requests', { keyPath: 'timestamp' });
      }
    };
  });
}

// Retry queued requests when back online
self.addEventListener('sync', event => {
  if (event.tag === 'retry-queued-requests') {
    event.waitUntil(retryQueuedRequests());
  }
});

async function retryQueuedRequests() {
  console.log('Retrying queued requests...');

  const requests = await getQueuedRequests();

  for (const requestData of requests) {
    try {
      const request = new Request(requestData.url, {
        method: requestData.method,
        headers: requestData.headers,
        body: requestData.body
      });

      const response = await fetch(request);

      if (response.ok) {
        // Remove from queue on success
        await removeQueuedRequest(requestData.timestamp);
        console.log('Successfully retried request:', requestData.url);
      } else {
        console.warn('Request still failed:', requestData.url, response.status);
      }
    } catch (error) {
      console.warn('Request retry failed:', requestData.url, error);
    }
  }
}

async function getQueuedRequests() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('pos-offline-queue', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction(['requests'], 'readonly');
      const store = transaction.objectStore('requests');
      const getAllRequest = store.getAll();

      getAllRequest.onsuccess = () => resolve(getAllRequest.result);
      getAllRequest.onerror = () => reject(getAllRequest.error);
    };
  });
}

async function removeQueuedRequest(timestamp) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('pos-offline-queue', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction(['requests'], 'readwrite');
      const store = transaction.objectStore('requests');
      const deleteRequest = store.delete(timestamp);

      deleteRequest.onsuccess = () => resolve();
      deleteRequest.onerror = () => reject(deleteRequest.error);
    };
  });
}

// Listen for messages from the main thread
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});