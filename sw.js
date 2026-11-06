// Avisos de mantención para cliente.html. Lee los datos que la página guardó en Cache Storage.
// shortcut: sin servidor, el aviso sale cuando Chrome Android hace su revisión diaria (app instalada) o al abrir la app;
// para avisos a hora exacta en todos los teléfonos (iPhone con la app cerrada) hace falta push desde un servidor (Web Push + VAPID).
const CACHE = "calora-cliente";
const hoy = () => new Date().toLocaleDateString("sv");
const entre = (a, b) => Math.round((new Date(b + "T12:00:00") - new Date(a + "T12:00:00")) / 864e5);

async function revisar() {
  if (self.Notification?.permission !== "granted") return;
  const c = await caches.open(CACHE);
  const leer = async (k) => { const r = await c.match(k); return r ? r.json() : {}; };
  const equipos = await leer("datos.json"), avisos = await leer("avisos.json");
  for (const e of Object.values(equipos)) {
    const m = e.mants[0];
    if (!m) continue;
    const d = entre(hoy(), m.proxima), k = e.id + ":" + m.proxima, ultimo = avisos[k];
    // una semana antes, el mismo día (o al pasar la fecha) y luego cada 7 días mientras siga atrasada
    if (d > 7 || (ultimo && entre(ultimo, hoy()) < 7 && !(d <= 0 && ultimo < m.proxima))) continue;
    await self.registration.showNotification(
      d < 0 ? "Tu termo está atrasado con su mantención" : d === 0 ? "Hoy toca la mantención de tu termo" : `En ${d} días toca la mantención de tu termo`,
      { body: [e.marca, e.litros].filter(Boolean).join(" ") + " · Toca aquí para agendar con Calora.", icon: "icon-192.png", badge: "icon-192.png", tag: k });
    avisos[k] = hoy();
  }
  await c.put("avisos.json", new Response(JSON.stringify(avisos)));
}

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("periodicsync", (e) => { if (e.tag === "calora-aviso") e.waitUntil(revisar()); });
self.addEventListener("message", (e) => { if (e.data === "revisar") e.waitUntil(revisar()); });
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((ws) => {
    const w = ws.find((x) => x.url.includes("cliente.html"));
    return w ? w.focus() : self.clients.openWindow("cliente.html");
  }));
});
