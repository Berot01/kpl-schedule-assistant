const CACHE = "kpl-assistant-v1";
const STATIC = ["./", "./index.html", "./style.css", "./app.js", "./manifest.webmanifest", "./icons/icon-192.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith("/data/schedule.json")) {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok) {const saved = response.clone(); caches.open(CACHE).then(cache => cache.put("./data/schedule.json", saved));}
      return response;
    }).catch(async () => (await caches.match("./data/schedule.json")) || Response.error()));
  } else {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
  }
});
