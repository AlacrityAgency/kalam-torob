/**
 * Service Worker کَلَم: کار بدون اینترنت در طبقات منفی پاساژها.
 * - پوسته برنامه (HTML/CSS/JS/فونت/لوگو) هنگام نصب کش می‌شود.
 * - درخواست‌های GET به API اول از شبکه و در صورت قطعی از آخرین پاسخ کش‌شده خوانده می‌شوند،
 *   پس صفحه کالا یا مسیری که قبلاً دیده شده، بدون اینترنت هم باز می‌شود.
 */
const VERSION = "kalam-v4";
const SHELL = ["/", "/index.html", "/app.css", "/app.js", "/logo.jpg", "/fonts/Vazirmatn-Variable.woff2", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    // شبکه اول؛ آخرین پاسخ موفق برای حالت آفلاین نگه داشته می‌شود
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || new Response(
          JSON.stringify({ detail: "اتصال اینترنت برقرار نیست و این صفحه قبلاً ذخیره نشده است." }),
          { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } },
        ))),
    );
    return;
  }

  // صفحه، CSS و JS: شبکه اول تا بعد از هر دیپلوی نسخه جدید دیده شود؛ بدون اینترنت از کش
  if (req.mode === "navigate" || /\.(html|css|js|webmanifest)$/.test(url.pathname)) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("/index.html"))),
    );
    return;
  }

  // فونت، لوگو و تصاویر: کش اول، سپس شبکه
  event.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok && (url.pathname.endsWith(".png") || url.pathname.endsWith(".woff2"))) {
        const copy = res.clone();
        caches.open(VERSION).then((cache) => cache.put(req, copy));
      }
      return res;
    }).catch(() => caches.match("/index.html"))),
  );
});
