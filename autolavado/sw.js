// Network-only on purpose: the app's data is live in the database, and caching the page
// would keep showing an old version after updates (as already happened once).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
