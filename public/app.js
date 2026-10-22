/**
 * کَلَم — دستیار خرید حضوری ترب
 * کنترلر فرانت‌اند: مسیریابی hash، صفحات خانه/جستجو/محصول/سبد و دستیار گفتگو.
 * همه داده‌های سرور پیش از درج در HTML با esc() ایمن می‌شوند.
 */

const API = "";
const LS_CART = "kalam_cart_v2";
const LS_HUB = "kalam_hub";
const LS_ROUTE = "kalam_route_cache";

const CATEGORY_LINKS = [
  ["گوشی موبایل", "گوشی موبایل"],
  ["لپ تاپ", "لپ‌تاپ"],
  ["هدفون", "هدفون و هندزفری"],
  ["ماوس", "ماوس و کیبورد"],
  ["شارژر", "شارژر"],
  ["کاور گوشی", "کیف و کاور"],
  ["ساعت هوشمند", "ساعت هوشمند"],
  ["کتانی", "کفش و کتانی"],
  ["دوربین مداربسته", "دوربین مداربسته"],
  ["کابل برق", "سیم و کابل"],
  ["دریل", "ابزار برقی"],
  ["پمپ آب", "پمپ آب"],
  ["موتور برق", "موتور برق"],
];

const POPULAR = ["ایرپاد", "Galaxy A55", "لپ تاپ ایسوس", "ماوس لاجیتک", "کتونی رانینگ", "دریل شارژی"];

const PROVIDERS = {
  snapp_pay: "اسنپ‌پی",
  torob_pay: "ترب‌پی",
  tara: "تارا",
  digi_pay: "دیجی‌پی",
  azki_vam: "ازکی‌وام",
};

const CHANNELS = {
  in_person: { label: "حضوری", cls: "tag-green", title: "پرداخت اقساطی با کارتخوان حضوری ثبت شده" },
  online: { label: "آنلاین", cls: "tag-gray", title: "فقط پرداخت اینترنتی ثبت شده" },
  unknown: { label: "کانال نامشخص", cls: "tag-amber", title: "در ترب ثبت نشده که اقساط حضوری هم ممکن است؛ پیش از رفتن بپرسید" },
};

// شرایط خرید قابل فیلتر در صفحه جستجو و صفحه کالا
const CONDITIONS = [
  ["credit", "خرید اقساطی"],
  ["open_now", "الان باز"],
  ["hours_known", "ساعت کاری مشخص"],
  ["fresh", "قیمت به‌روز (۱۴ روز اخیر)"],
  ["include_copies", "نمایش آفرهای غیراصل/مشکوک"],
];

const STRATEGIES = {
  same_hub: { label: "مسیر یک پاساژ", hint: "همه اقلام از یک مرکز خرید، با کمترین تعداد مغازه و بالا رفتن یک‌طرفه از طبقات." },
  single_stop: { label: "یک مغازه", hint: "همه اقلام از یک فروشگاه با یک فاکتور؛ بدون جابه‌جایی." },
  bargain: { label: "ارزان‌ترین", hint: "ارزان‌ترین قیمت هر کالا در کل تهران؛ ممکن است چند مرکز خرید را شامل شود." },
};

// پاساژهایی که نامشان در آدرس فروشگاه‌ها می‌آید (محدوده‌های دیتاست، محله‌اند نه پاساژ)
const MALLS = ["چارسو", "علاءالدین", "پایتخت", "امجد", "مرکز کامپیوتر ایران", "مرکز کامپیوتر نور", "کوروش", "قائم"];

const CHAT_PROMPTS = [
  "گوشی A55 قسطی در چارسو",
  "دنبال یه کفش کتونی خوب برای پیاده‌روی هستم",
  "ارزون‌ترش کدومه؟",
  "جمعه کدوم مغازه‌ها بازن؟",
  "فروشگاه‌های دارای اقساط اسنپ پی",
  "مسیر خرید سبدم رو بچین",
];

const ICONS = {
  box: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v8"/></svg>',
  store: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h16l-1-5H5L4 9Zm0 0v11h16V9M9 20v-6h6v6"/></svg>',
  pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
  phone: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg>',
  route: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7"/></svg>',
  alert: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/></svg>',
  cart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/><circle cx="10" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/></svg>',
  trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  filter: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6 8v5l-4 2v-7L4 5Z"/></svg>',
  clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  shield: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></svg>',
  card: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg>',
  walk: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="13" cy="4" r="2"/><path d="m9 21 2-6 3 2v4M7 12l3-4 4 1 2 4 3 1M10 8l-1 5"/></svg>',
  save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h11l3 3v15H5V3Z"/><path d="M8 3v5h7V3M8 21v-7h8v7"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
  tag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12V4h8l10 10-8 8L3 12Z"/><circle cx="7.5" cy="8" r="1.5"/></svg>',
  globe: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
  insta: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.5"/><circle cx="16.8" cy="7.2" r=".8"/></svg>',
  chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H8l-4 4V5Z"/></svg>',
};

const small = (icon) => icon.replace("<svg", '<svg style="width:14px;height:14px"');

/* ---------------- Utilities ---------------- */

function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const faNum = (n) => Number(n || 0).toLocaleString("fa-IR");

// دیتاست ترب مقادیر خالی را با رشته "null" ذخیره می‌کند
const clean = (v) => (v === null || v === undefined || v === "null" || v === "" ? null : v);

function priceHtml(n, withFrom = false) {
  if (!n) return '<span class="faint">قیمت نامشخص؛ استعلام در محل</span>';
  return `${withFrom ? '<span class="from">از</span>' : ""}${faNum(n)} <span class="unit">تومان</span>`;
}

function firstImage(raw) {
  if (!raw) return null;
  let urls = [raw];
  if (typeof raw === "string" && raw.trim().startsWith("[")) {
    try { urls = JSON.parse(raw); } catch (e) { return null; }
  }
  const url = (Array.isArray(urls) ? urls : []).find((u) => typeof u === "string" && /^https?:\/\//.test(u));
  return url || null;
}

function thumbHtml(rawImage, alt = "") {
  const url = firstImage(rawImage);
  if (url) {
    return `<div class="product-thumb"><img src="${esc(url)}" alt="${esc(alt)}" loading="lazy" referrerpolicy="no-referrer" data-fallback></div>`;
  }
  return `<div class="product-thumb"><div class="thumb-placeholder">${ICONS.box}</div></div>`;
}

function freshnessText(days) {
  if (days === null || days === undefined) return "تاریخ قیمت نامشخص";
  if (days <= 0) return "قیمت امروز به‌روز شده";
  if (days === 1) return "قیمت دیروز به‌روز شده";
  return `قیمت ${faNum(days)} روز پیش به‌روز شده`;
}

function parsePayment(raw) {
  if (!raw || raw === "null") return [];
  try {
    const data = typeof raw === "string" ? JSON.parse(raw) : raw;
    return Array.isArray(data) ? data.filter((o) => o && typeof o === "object") : [];
  } catch (e) {
    return [];
  }
}

function creditTags(providers) {
  return providers.map((p) => {
    const name = PROVIDERS[p.provider] || p.provider_label || p.provider_name || p.provider || "";
    const ch = CHANNELS[p.channel] || CHANNELS.unknown;
    return `<span class="tag ${ch.cls}" title="${esc(ch.title)}">${esc(name)} · ${esc(ch.label)}</span>`;
  }).join("");
}

function hoursHtml(h) {
  if (!h) return "";
  const cls = { open: "dot-high", closed: "dot-low" }[h.state] || "dot-medium";
  const friday = h.friday_closed ? " · جمعه‌ها تعطیل" : "";
  return `<span><span class="dot ${cls}"></span>${esc(h.label)}${friday}</span>`;
}

function verifiedLinks(shop) {
  const links = [];
  const insta = clean(shop.instagram);
  const site = clean(shop.website_url);
  if (insta) {
    const handle = String(insta).replace(/^@/, "").replace(/^https?:\/\/(www\.)?instagram\.com\//, "").replace(/\/.*$/, "");
    if (/^[A-Za-z0-9._]{1,30}$/.test(handle)) {
      links.push(`<a class="tag tag-blue" href="https://instagram.com/${esc(handle)}" target="_blank" rel="noopener nofollow">${small(ICONS.insta)} اینستاگرام</a>`);
    }
  }
  if (site && /^https?:\/\//.test(site)) {
    links.push(`<a class="tag tag-blue" href="${esc(site)}" target="_blank" rel="noopener nofollow">${small(ICONS.globe)} وب‌سایت</a>`);
  }
  return links.join("");
}

function locationLine(parsed, hub) {
  if (!parsed) return "";
  // اطلاعات نامشخص حذف نمی‌شوند؛ صریحاً «ثبت‌نشده» نوشته می‌شوند
  const parts = [parsed.mall_name, parsed.floor_label || "طبقه نامشخص", parsed.unit_number || "واحد ثبت‌نشده"]
    .filter((p) => p);
  if (hub && parsed.mall_name !== hub && !String(parsed.mall_name || "").includes(hub)) parts.unshift(hub);
  return `${ICONS.pin}${parts.map((p) => esc(p)).join('<span class="sep">·</span>')}`;
}

async function getJSON(url, options) {
  const res = await fetch(API + url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function postJSON(url, body) {
  return getJSON(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

function readStore(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch (e) {
    return fallback;
  }
}

function writeStore(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* حافظه در دسترس نیست */ }
}

/* ---------------- App ---------------- */

class KalamApp {
  constructor() {
    this.view = document.getElementById("view");
    this.cart = readStore(LS_CART, []);
    this.hub = readStore(LS_HUB, null);
    this.hubs = [];
    this.strategy = "same_hub";
    this.searchState = { sort: "relevant", minPrice: "", maxPrice: "", conditions: {} };
    this.sellerFilter = { hub: null, conditions: {} };
    this.lastResults = [];
    this.productCache = {};
    this.activeProductId = null;
    this.activeShopId = null;
    // حافظه گفتگو: وضعیت جستجوی قبلی که سرور برگردانده و با پیام بعدی فرستاده می‌شود
    this.chatState = null;
    this.tree = null;

    this.renderCategoryNav();
    this.bindGlobal();
    this.updateCartBadge();
    this.renderHubLabel();
    this.renderChatPrompts();
    this.loadHubs();
    this.loadHealth();

    window.addEventListener("hashchange", () => this.route());
    this.route();
  }

  /* ---------- Global wiring ---------- */

  bindGlobal() {
    document.getElementById("header-search").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = e.target.q.value.trim();
      if (q) this.go(`/search?q=${encodeURIComponent(q)}`);
    });

    const hubBtn = document.getElementById("hub-btn");
    const hubMenu = document.getElementById("hub-menu");
    hubBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = hubMenu.hidden;
      hubMenu.hidden = !open;
      hubBtn.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (e) => {
      if (!hubMenu.hidden && !hubMenu.contains(e.target)) {
        hubMenu.hidden = true;
        hubBtn.setAttribute("aria-expanded", "false");
      }
    });

    document.getElementById("assistant-fab").addEventListener("click", () => this.toggleAssistant());
    document.getElementById("chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      const text = input.value.trim();
      if (text) {
        input.value = "";
        this.sendChat(text);
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!document.getElementById("modal").hidden) this.closeModal();
        else if (!document.getElementById("assistant").hidden) this.toggleAssistant(false);
      }
    });

    // تصاویر شکسته را با جای‌خالی جایگزین کن
    document.addEventListener("error", (e) => {
      const img = e.target;
      if (img.tagName === "IMG" && img.hasAttribute("data-fallback")) {
        img.parentElement.innerHTML = `<div class="thumb-placeholder">${ICONS.box}</div>`;
      }
    }, true);

    // همه دکمه‌های داینامیک با data-action مدیریت می‌شوند (بدون onclick داخل HTML)
    document.addEventListener("click", (e) => {
      const el = e.target.closest("[data-action]");
      if (!el) return;
      const d = el.dataset;
      switch (d.action) {
        case "close-modal": this.closeModal(); break;
        case "close-assistant": this.toggleAssistant(false); break;
        case "clear-chat": this.clearChat(); break;
        case "set-hub": this.setHub(d.hub || null); break;
        case "add-cart": this.addToCart(d.id); break;
        case "remove-cart": this.removeFromCart(d.id); break;
        case "clear-cart": this.cart = []; this.saveCart(); this.renderCart(); break;
        case "strategy": this.strategy = d.strategy; this.renderCart(); break;
        case "sort": this.searchState.sort = d.sort; this.renderResults(); break;
        case "search-condition": this.toggleSearchCondition(d.key); break;
        case "seller-condition": this.toggleSellerCondition(d.key); break;
        case "simulate": this.runSimulation(d.offer, d.question); break;
        case "tree-option": this.answerTree(Number(d.step), Number(d.index)); break;
        case "toggle-filters": document.getElementById("filters").classList.toggle("open"); break;
        case "seller-filter": this.filterSellers(d.hub || ""); break;
        case "wayfinding": this.showWayfinding(d.shop); break;
        case "dossier": this.showDossier(d.shop, d.product, Number(d.price || 0), d.offer); break;
        case "panic": this.showPanic(d.product, d.shop, d.shopName); break;
        case "copy": this.copyText(d.target); break;
        case "save-route": this.saveRouteOffline(); break;
        case "chat-prompt": this.sendChat(d.text); break;
        case "go": this.closeModal(); this.go(d.href); break;
      }
    });
  }

  go(path) {
    if (location.hash === `#${path}`) this.route();
    else location.hash = path;
  }

  route() {
    // هر رندر یک شناسه دارد تا پاسخ دیرِ صفحه قبلی صفحه جدید را بازنویسی نکند
    this.renderSeq = (this.renderSeq || 0) + 1;
    const hash = location.hash.replace(/^#/, "") || "/";
    const [path, query = ""] = hash.split("?");
    const params = new URLSearchParams(query);
    document.body.classList.toggle("is-home", path === "/");
    this.closeModal();
    window.scrollTo(0, 0);

    const headerInput = document.getElementById("header-search-input");
    headerInput.value = path === "/search" ? params.get("q") || "" : "";
    this.highlightCategory(path === "/search" ? params.get("q") : null);

    if (path === "/search") return this.renderSearch(params.get("q") || "");
    if (path.startsWith("/product/")) return this.renderProduct(decodeURIComponent(path.slice(9)));
    if (path === "/cart") return this.renderCart();
    if (path === "/about") return this.renderAbout();
    return this.renderHome();
  }

  isStale(seq) {
    return seq !== this.renderSeq;
  }

  setView(html, title) {
    this.view.innerHTML = html;
    document.title = title ? `${title} | کَلَم` : "کَلَم | دستیار خرید حضوری ترب";
  }

  /* ---------- Header pieces ---------- */

  renderCategoryNav() {
    document.getElementById("cat-nav").innerHTML = CATEGORY_LINKS
      .map(([q, label]) => `<a href="#/search?q=${encodeURIComponent(q)}" data-q="${esc(q)}">${esc(label)}</a>`)
      .join("");
  }

  highlightCategory(q) {
    document.querySelectorAll("#cat-nav a").forEach((a) => a.classList.toggle("active", !!q && a.dataset.q === q));
  }

  async loadHubs() {
    try {
      const data = await getJSON("/api/hubs");
      this.hubs = data.hubs || [];
    } catch (e) {
      this.hubs = [];
    }
    this.renderHubMenu();
    if (document.body.classList.contains("is-home")) this.renderHomeHubs();
  }

  async loadHealth() {
    try {
      const h = await getJSON("/api/health");
      this.health = h;
      const banner = document.getElementById("data-banner");
      if (h.data_source === "sample") {
        banner.innerHTML = `${small(ICONS.alert)} این نسخه با <strong>داده نمونه و ساختگی</strong> اجرا شده است؛ برای داده واقعی، دیتاست ترب را با <code>scripts/build_db.py</code> بارگذاری کنید.`;
        banner.hidden = false;
      }
    } catch (e) { /* سرور در دسترس نیست؛ صفحه‌ها خطای خود را نشان می‌دهند */ }
  }

  renderHubMenu() {
    const items = [{ name: null, shop_count: null }, ...this.hubs];
    const known = new Set(this.hubs.map((h) => h.name));
    const malls = MALLS.filter((m) => !known.has(m));
    document.getElementById("hub-menu").innerHTML = items.map((h) => `
      <li><button type="button" role="option" data-action="set-hub" data-hub="${esc(h.name || "")}" aria-selected="${(h.name || null) === this.hub}">
        <span>${h.name ? esc(h.name) : "همه محدوده‌های تهران"}</span>
        ${h.shop_count ? `<small>${faNum(h.shop_count)} فروشگاه</small>` : ""}
      </button></li>`).join("") +
      `<li class="hub-menu-label">پاساژها و مراکز خرید</li>` +
      malls.map((m) => `
      <li><button type="button" role="option" data-action="set-hub" data-hub="${esc(m)}" aria-selected="${m === this.hub}">
        <span>${esc(m)}</span><small>از روی آدرس</small>
      </button></li>`).join("");
  }

  renderHubLabel() {
    document.getElementById("hub-btn-label").textContent = this.hub || "همه محدوده‌ها";
  }

  setHub(hub) {
    this.hub = hub;
    writeStore(LS_HUB, hub);
    document.getElementById("hub-menu").hidden = true;
    document.getElementById("hub-btn").setAttribute("aria-expanded", "false");
    this.renderHubLabel();
    this.renderHubMenu();
    this.toast(hub ? `محدوده خرید: ${hub}` : "جستجو در همه محدوده‌های تهران");
    const hash = location.hash.replace(/^#/, "");
    if (hash.startsWith("/search") || hash.startsWith("/product/") || hash === "/cart") this.route();
  }

  /* ---------- Home ---------- */

  async renderHome() {
    this.setView(`
      <section class="container home-hero">
        <img src="./logo.jpg" alt="" class="home-logo">
        <h1>کَلَم</h1>
        <p>کمترین قیمت حضوری، آدرس دقیق طبقه و واحد، و مسیر خرید در پاساژهای تهران</p>
        <form class="search-box home-search" id="home-search" role="search">
          <input type="search" name="q" placeholder="نام کالا را وارد کنید" autocomplete="off" aria-label="جستجوی کالا" autofocus>
          <button type="submit" class="search-box-btn" aria-label="جستجو">${ICONS.search}</button>
        </form>
        <div class="popular">
          <span>جستجوهای پرطرفدار:</span>
          ${POPULAR.map((q) => `<a class="chip" href="#/search?q=${encodeURIComponent(q)}">${esc(q)}</a>`).join("")}
        </div>
      </section>

      <section class="container">
        <div class="section-title"><h2>مراکز خرید</h2></div>
        <div class="hub-grid" id="home-hubs">${'<div class="hub-card skeleton" style="height:70px"></div>'.repeat(4)}</div>

        <div class="section-title"><h2>پرفروشنده‌ترین کالاها در بازار حضوری</h2></div>
        <div class="product-grid cols-6" id="home-products">${this.skeletonCards(6)}</div>

        <div class="value-row">
          <div class="value-item">${ICONS.route}<div><strong>مسیر خرید چندقلمی</strong><span>چند کالا را در یک پاساژ با کمترین رفت‌وآمد بین طبقات بخرید.</span></div></div>
          <div class="value-item">${ICONS.pin}<div><strong>آدرس طبقه و واحد</strong><span>نام پاساژ، طبقه و شماره واحد هر مغازه، با راهنمای قدم‌به‌قدم.</span></div></div>
          <div class="value-item">${ICONS.phone}<div><strong>استعلام پیش از رفتن</strong><span>متن آماده تماس برای پرسیدن موجودی و قیمت روز.</span></div></div>
          <div class="value-item">${ICONS.alert}<div><strong>مغازه بسته بود؟</strong><span>نزدیک‌ترین فروشگاه جایگزین در همان طبقه یا همان پاساژ.</span></div></div>
        </div>
      </section>`);

    document.getElementById("home-search").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = e.target.q.value.trim();
      if (q) this.go(`/search?q=${encodeURIComponent(q)}`);
    });

    this.renderHomeHubs();
    const seq = this.renderSeq;
    try {
      const data = await getJSON("/api/products/suggested");
      const el = document.getElementById("home-products");
      if (!el || this.isStale(seq)) return;
      const items = data.suggested || [];
      el.innerHTML = items.length ? items.map((p) => this.productCardHtml(p)).join("") : this.emptyHtml("کالایی برای نمایش نیست", "پایگاه داده خالی است.");
    } catch (e) {
      const el = document.getElementById("home-products");
      if (el) el.outerHTML = this.errorHtml();
    }
  }

  renderHomeHubs() {
    const el = document.getElementById("home-hubs");
    if (!el || !this.hubs.length) return;
    el.innerHTML = this.hubs.map((h) => `
      <button type="button" class="hub-card" data-action="set-hub" data-hub="${esc(h.name)}">
        <span class="hub-icon">${ICONS.store}</span>
        <span><strong>${esc(h.name)}</strong><small>${faNum(h.shop_count)} فروشگاه</small></span>
      </button>`).join("");
  }

  /* ---------- Cards & shared HTML ---------- */

  productCardHtml(p) {
    const title = p.persian_title || p.title || "";
    const shops = p.available_offline_shops_count || 0;
    return `
      <a class="product-card" href="#/product/${encodeURIComponent(p.product_id)}">
        ${thumbHtml(p.image_url, title)}
        <h3 class="product-title">${esc(title)}</h3>
        <div class="product-price">${priceHtml(p.min_price_toman, shops > 1)}</div>
        <div class="product-shops">${shops ? `در ${faNum(shops)} فروشگاه حضوری` : "فروشگاه حضوری ندارد"}</div>
      </a>`;
  }

  skeletonCards(n) {
    return Array.from({ length: n }, () => `
      <div class="product-card">
        <div class="product-thumb skeleton"></div>
        <div class="skeleton" style="height:12px;margin-bottom:8px"></div>
        <div class="skeleton" style="height:12px;width:60%;margin-bottom:16px"></div>
        <div class="skeleton" style="height:14px;width:50%"></div>
      </div>`).join("");
  }

  emptyHtml(title, text, action = "") {
    return `<div class="empty" style="grid-column:1/-1">${ICONS.search}<strong>${esc(title)}</strong><div>${esc(text)}</div>${action}</div>`;
  }

  errorHtml() {
    return `<div class="panel empty">${ICONS.alert}<strong>ارتباط با سرور برقرار نشد</strong><div>اتصال را بررسی کنید و دوباره تلاش کنید.</div></div>`;
  }

  /* ---------- Search ---------- */

  async renderSearch(q) {
    if (!q) return this.go("/");
    if (this.searchQuery !== q) this.searchState.sort = "relevant";
    this.searchQuery = q;
    const seq = this.renderSeq;
    if (!document.getElementById("results") || document.body.dataset.searchQ !== q) {
      document.body.dataset.searchQ = q;
      this.setView(`
        <div class="container">
          <nav class="breadcrumb" aria-label="مسیر صفحه"><a href="#/">کَلَم</a><span>/</span><span>جستجوی «${esc(q)}»</span></nav>
          <div class="search-layout">
            <aside class="panel filters" id="filters"></aside>
            <section>
              <div class="panel results-head" id="results-head">
                <h1>«${esc(q)}»<small>در حال جستجو…</small></h1>
              </div>
              <div class="product-grid" id="results">${this.skeletonCards(8)}</div>
            </section>
          </div>
        </div>`, `جستجوی ${q}`);
    }

    // بودجه و شرایط خرید روی سرور و در سطح آفر اعمال می‌شوند (نه فقط روی کمترین قیمت کالا)
    const st = this.searchState;
    const params = new URLSearchParams({ q, limit: "60" });
    if (this.hub) params.set("hub", this.hub);
    if (Number(st.minPrice) > 0) params.set("min_price", String(Number(st.minPrice)));
    if (Number(st.maxPrice) > 0) params.set("max_price", String(Number(st.maxPrice)));
    Object.entries(st.conditions).forEach(([k, v]) => { if (v) params.set(k, "true"); });
    try {
      const data = await getJSON(`/api/search?${params}`);
      if (this.isStale(seq)) return;
      this.lastResults = data.products || [];
      this.renderResults();
    } catch (e) {
      const el = document.getElementById("results");
      if (el) el.outerHTML = this.errorHtml();
    }
  }

  toggleSearchCondition(key) {
    this.searchState.conditions[key] = !this.searchState.conditions[key];
    this.renderSearch(this.searchQuery);
  }

  renderResults() {
    const q = this.searchQuery;
    const s = this.searchState;
    let items = [...this.lastResults];
    const byPrice = (a, b) => (a.min_price_toman || Infinity) - (b.min_price_toman || Infinity);
    if (s.sort === "cheap") items.sort(byPrice);
    if (s.sort === "expensive") items.sort((a, b) => (b.min_price_toman || 0) - (a.min_price_toman || 0));
    if (s.sort === "shops") items.sort((a, b) => (b.available_offline_shops_count || 0) - (a.available_offline_shops_count || 0));

    const active = CONDITIONS.filter(([k]) => s.conditions[k]).map(([, l]) => l);
    const budget = [Number(s.minPrice) > 0 ? `از ${faNum(s.minPrice)}` : "", Number(s.maxPrice) > 0 ? `تا ${faNum(s.maxPrice)} تومان` : ""].filter(Boolean).join(" ");
    const summary = [this.hub ? `در ${this.hub}` : "", budget, ...active].filter(Boolean).join("، ");

    const sorts = [["relevant", "مرتبط‌ترین"], ["cheap", "ارزان‌ترین"], ["expensive", "گران‌ترین"], ["shops", "بیشترین فروشگاه"]];
    const head = document.getElementById("results-head");
    if (!head) return;
    head.innerHTML = `
      <h1>«${esc(q)}»<small>${faNum(items.length)} کالا${summary ? ` · ${esc(summary)}` : ""}</small></h1>
      <div class="sort-row">
        <button type="button" class="btn btn-ghost btn-sm filter-toggle" data-action="toggle-filters">${ICONS.filter} فیلترها${active.length || budget ? ` (${faNum(active.length + (budget ? 1 : 0))})` : ""}</button>
        <span>مرتب‌سازی:</span>
        ${sorts.map(([k, l]) => `<button type="button" data-action="sort" data-sort="${k}" class="${s.sort === k ? "active" : ""}">${l}</button>`).join("")}
      </div>`;

    const hubOptions = [{ name: null }, ...this.hubs];
    const filters = document.getElementById("filters");
    const wasOpen = filters.classList.contains("open");
    filters.innerHTML = `
      <div class="filter-group">
        <h3>شرایط خرید</h3>
        ${CONDITIONS.map(([k, l]) => `
          <button type="button" class="filter-option check ${s.conditions[k] ? "active" : ""}" data-action="search-condition" data-key="${k}" aria-pressed="${!!s.conditions[k]}">
            <span><span class="checkbox"></span>${esc(l)}</span>
          </button>`).join("")}
      </div>
      <div class="filter-group">
        <h3>بودجه (تومان)</h3>
        <form class="price-inputs" id="price-form">
          <input type="number" inputmode="numeric" min="0" step="100000" name="min" placeholder="از" value="${esc(s.minPrice)}" aria-label="حداقل قیمت">
          <input type="number" inputmode="numeric" min="0" step="100000" name="max" placeholder="تا" value="${esc(s.maxPrice)}" aria-label="حداکثر قیمت">
          <button type="submit" class="btn btn-ghost btn-sm" style="grid-column:1/-1">اعمال بودجه</button>
        </form>
      </div>
      <div class="filter-group">
        <h3>محدوده</h3>
        ${hubOptions.map((h) => `
          <button type="button" class="filter-option ${(h.name || null) === this.hub ? "active" : ""}" data-action="set-hub" data-hub="${esc(h.name || "")}">
            <span><span class="radio"></span>${h.name ? esc(h.name) : "همه محدوده‌ها"}</span>
            ${h.shop_count ? `<span class="faint">${faNum(h.shop_count)}</span>` : ""}
          </button>`).join("")}
      </div>`;
    filters.classList.toggle("open", wasOpen);
    document.getElementById("price-form").addEventListener("submit", (e) => {
      e.preventDefault();
      s.minPrice = e.target.min.value;
      s.maxPrice = e.target.max.value;
      this.renderSearch(q);
    });

    const grid = document.getElementById("results");
    if (!items.length) {
      const hasFilters = this.hub || budget || active.length;
      grid.innerHTML = this.emptyHtml(
        "کالایی پیدا نشد",
        hasFilters ? `برای «${q}» با این شرایط فروشگاه حضوری پیدا نشد. یکی از شرط‌ها را بردارید.` : `برای «${q}» نتیجه‌ای پیدا نشد. عبارت کوتاه‌تری را امتحان کنید.`,
        this.hub ? `<div style="margin-top:14px"><button type="button" class="btn btn-outline btn-sm" data-action="set-hub" data-hub="">جستجو در همه محدوده‌ها</button></div>` : ""
      );
      return;
    }
    grid.innerHTML = items.map((p) => this.productCardHtml(p)).join("");
  }

  /* ---------- Product ---------- */

  async renderProduct(id) {
    this.activeProductId = id;
    const seq = this.renderSeq;
    this.setView(`<div class="container"><div style="height:16px"></div><div class="panel product-hero"><div class="product-thumb skeleton"></div><div><div class="skeleton" style="height:18px;margin-bottom:12px"></div><div class="skeleton" style="height:18px;width:60%"></div></div></div></div>`);
    let data, comp;
    const hubParam = this.hub ? `?hub=${encodeURIComponent(this.hub)}` : "";
    try {
      [data, comp] = await Promise.all([
        getJSON(`/api/product/${encodeURIComponent(id)}${hubParam}`),
        getJSON(`/api/complementary/${encodeURIComponent(id)}`).catch(() => null),
      ]);
    } catch (e) {
      if (this.isStale(seq)) return;
      this.setView(`<div class="container" style="padding-top:24px"><div class="panel empty">${ICONS.box}<strong>کالا پیدا نشد</strong><div>ممکن است این کالا از ترب حذف شده باشد.</div><div style="margin-top:14px"><a class="btn btn-outline btn-sm" href="#/">بازگشت به خانه</a></div></div></div>`);
      return;
    }
    if (this.isStale(seq)) return;

    const p = data.product;
    const offers = data.offers || [];
    this.currentProduct = p;
    this.productCache[id] = { id, title: p.title, price: p.min_price, image: p.image_url };
    this.currentOffers = offers;
    const inCart = this.cart.some((c) => c.id === id);
    const hubCount = new Set(offers.map((o) => o.shop.location_label || "سایر")).size;

    // محدوده انتخاب‌شده در هدر، اگر آفری در آن هست، فیلتر پیش‌فرض فروشگاه‌هاست
    const hubHasOffers = this.hub && offers.some((o) => this.placeMatches(this.hub, o.shop));
    this.sellerFilter = { hub: hubHasOffers ? this.hub : null, conditions: {} };

    const specs = p.specs || [];
    const categoryOnly = data.category_only_shops || [];

    this.setView(`
      <div class="container">
        <nav class="breadcrumb" aria-label="مسیر صفحه">
          <a href="#/">کَلَم</a><span>/</span>
          ${p.category ? `<a href="#/search?q=${encodeURIComponent(p.category)}">${esc(p.category)}</a><span>/</span>` : ""}
          ${p.brand ? `<a href="#/search?q=${encodeURIComponent(p.brand)}">${esc(p.brand)}</a>` : ""}
        </nav>

        <section class="panel product-hero">
          ${thumbHtml(p.image_url, p.title)}
          <div>
            <h1>${esc(p.title)}</h1>
            <div class="product-meta-row">
              <span>${ICONS.store} ${faNum(p.offline_shops_count)} فروشگاه حضوری</span>
              <span>${ICONS.pin} ${faNum(hubCount)} محدوده</span>
              <span>${ICONS.tag} برند: ${p.brand ? esc(p.brand) : "ثبت نشده"}</span>
            </div>
            <div class="price-box">
              <span class="label">کمترین قیمت حضوری</span>
              <span class="value">${p.min_price ? `${faNum(p.min_price)} <small>تومان</small>` : "نامشخص"}</span>
              ${p.max_price && p.max_price !== p.min_price ? `<span class="range">تا ${faNum(p.max_price)} تومان در فروشگاه‌های دیگر</span>` : ""}
              ${p.flagged_offers ? `<span class="range">${faNum(p.flagged_offers)} آفر غیراصل یا با قیمت غیرعادی در این محاسبه نیامده است</span>` : ""}
            </div>
            <div class="hero-actions">
              ${inCart
                ? `<a class="btn btn-outline" href="#/cart">${ICONS.cart} در سبد حضوری است؛ مشاهده مسیر</a>`
                : `<button type="button" class="btn btn-primary" data-action="add-cart" data-id="${esc(id)}">${ICONS.cart} افزودن به سبد خرید حضوری</button>`}
              <a class="btn btn-ghost" href="#sellers">مقایسه فروشگاه‌ها</a>
            </div>
          </div>
        </section>

        <section class="panel" id="sellers" style="margin-top:16px">
          <div class="panel-head">
            <h2>فروشگاه‌های حضوری</h2>
            <span class="faint" style="font-size:12px" id="seller-count"></span>
          </div>
          <div class="seller-filters" id="seller-filters"></div>
          <div id="seller-list"></div>
        </section>

        ${specs.length ? `
        <section class="panel" style="margin-top:16px">
          <div class="panel-head"><h2>مشخصات فنی</h2></div>
          <dl class="spec-table">
            ${specs.map((r) => `<div><dt>${esc(r.name)}</dt><dd>${esc(r.value)}</dd></div>`).join("")}
          </dl>
        </section>` : ""}

        ${categoryOnly.length ? `
        <section class="panel" style="margin-top:16px">
          <div class="panel-head">
            <h2>فروشگاه‌های هم‌صنف</h2>
            <span class="tag tag-amber">موجودی نامشخص</span>
          </div>
          <p class="panel-note">این فروشگاه‌ها در ترب فقط دسته فعالیت «${esc(p.category)}» را ثبت کرده‌اند و آفری برای این کالا ندارند. دسته فعالیت نشانه موجود بودن کالا نیست؛ فقط با استعلام مراجعه کنید.</p>
          ${categoryOnly.map((sh) => `
            <div class="seller-row">
              <div>
                <div class="seller-name">${esc(sh.name)} ${verifiedLinks(sh)}</div>
                <div class="seller-loc">${locationLine(sh.parsed_address, sh.location_label)}</div>
                <div class="seller-sub">${hoursHtml(sh.hours)}</div>
              </div>
              <div class="seller-side">
                <button type="button" class="btn btn-outline btn-sm" data-action="wayfinding" data-shop="${esc(sh.shop_id)}">${ICONS.route} مسیر تا مغازه</button>
              </div>
            </div>`).join("")}
        </section>` : ""}

        ${comp && comp.recommendations && comp.recommendations.length ? `
        <section class="panel" style="margin-top:16px">
          <div class="panel-head"><h2>کالاهای مکمل</h2><span class="faint" style="font-size:12px">لوازمی که معمولاً همراه این کالا خریده می‌شوند</span></div>
          <div class="h-scroll">
            ${this.uniqueByProduct(comp.recommendations).map((c) => `
              <a class="mini-card" href="#/product/${encodeURIComponent(c.product_id)}">
                ${c.reason ? `<span class="tag tag-gray">${esc(c.reason)}</span>` : ""}
                <h3 class="product-title">${esc(c.title)}</h3>
                <div class="product-price">${priceHtml(c.price_toman)}</div>
                <div class="where">${esc(c.shop_name)} · ${esc(c.location_description || c.location_label || "")}</div>
              </a>`).join("")}
          </div>
        </section>` : ""}
      </div>`, p.title);
    this.renderSellers();
  }

  placeMatches(place, shop) {
    if (!place) return true;
    if (shop.location_label === place) return true;
    return !!shop.address && shop.address.replace(/\u200c/g, " ").includes(place);
  }

  offerPasses(o, cond) {
    const sh = o.shop;
    if (!cond.include_copies && (o.is_copy || o.price_suspect)) return false;
    if (cond.credit && !(sh.credit_info && sh.credit_info.has_credit)) return false;
    if (cond.open_now && !(sh.hours && sh.hours.state === "open")) return false;
    if (cond.hours_known && !(sh.hours && sh.hours.known)) return false;
    if (cond.fresh) {
      const d = o.stock_certainty && o.stock_certainty.days_since_update;
      if (d === null || d === undefined || d > 14) return false;
    }
    return true;
  }

  renderSellers() {
    const list = document.getElementById("seller-list");
    if (!list) return;
    const f = this.sellerFilter;
    const offers = this.currentOffers || [];
    const byCond = offers.filter((o) => this.offerPasses(o, f.conditions));
    const shown = byCond.filter((o) => this.placeMatches(f.hub, o.shop));

    const hubCounts = {};
    byCond.forEach((o) => { const h = o.shop.location_label || "سایر"; hubCounts[h] = (hubCounts[h] || 0) + 1; });
    if (f.hub && !hubCounts[f.hub]) hubCounts[f.hub] = byCond.filter((o) => this.placeMatches(f.hub, o.shop)).length;

    document.getElementById("seller-filters").innerHTML = `
      <button type="button" class="chip ${!f.hub ? "active" : ""}" data-action="seller-filter" data-hub="">همه <span class="chip-count">${faNum(byCond.length)}</span></button>
      ${Object.entries(hubCounts).map(([h, n]) => `<button type="button" class="chip ${f.hub === h ? "active" : ""}" data-action="seller-filter" data-hub="${esc(h)}">${esc(h)} <span class="chip-count">${faNum(n)}</span></button>`).join("")}
      <span class="chip-sep" aria-hidden="true"></span>
      ${CONDITIONS.map(([k, l]) => `<button type="button" class="chip ${f.conditions[k] ? "active" : ""}" data-action="seller-condition" data-key="${k}" aria-pressed="${!!f.conditions[k]}">${esc(l)}</button>`).join("")}`;

    const hidden = offers.length - byCond.length;
    document.getElementById("seller-count").textContent =
      `${faNum(shown.length)} آفر` + (hidden && !f.conditions.include_copies ? ` · ${faNum(offers.filter((o) => o.is_copy || o.price_suspect).length)} آفر غیراصل/مشکوک پنهان است` : "");

    list.innerHTML = shown.length
      ? shown.map((o) => this.sellerRowHtml(o, this.currentProduct)).join("")
      : this.emptyHtml("با این شرایط فروشگاهی نیست", "یکی از شرط‌ها یا محدوده را بردارید.");
  }

  toggleSellerCondition(key) {
    this.sellerFilter.conditions[key] = !this.sellerFilter.conditions[key];
    this.renderSellers();
  }

  uniqueByProduct(items) {
    const seen = new Set();
    return items.filter((c) => !seen.has(c.product_id) && seen.add(c.product_id));
  }

  sellerRowHtml(o, product) {
    const s = o.shop;
    const sc = o.stock_certainty || {};
    const level = (sc.badge && sc.badge.type) || "low";
    const providers = (s.credit_info && s.credit_info.badges) || [];
    const note = [clean(o.seller_title), clean(o.description)].filter(Boolean).join(" — ");
    return `
      <div class="seller-row ${o.is_copy || o.price_suspect ? "flagged" : ""}">
        <div>
          <div class="seller-name">
            ${esc(s.name)}
            ${o.is_copy ? '<span class="tag tag-red">غیراصل اعلام‌شده</span>' : ""}
            ${o.price_suspect ? '<span class="tag tag-red">قیمت غیرعادی</span>' : ""}
            ${verifiedLinks(s)}
          </div>
          <div class="seller-loc">${locationLine(s.parsed_address, s.location_label)}</div>
          ${note ? `<div class="seller-note">توضیح فروشنده: ${esc(note)}</div>` : ""}
          <div class="seller-sub">
            <span><span class="dot dot-${esc(level)}"></span>${esc(freshnessText(sc.days_since_update))} · ${esc(sc.badge ? sc.badge.label : "")}</span>
            ${hoursHtml(s.hours)}
            <span>${small(ICONS.shield)} ${clean(o.warranty) ? esc(o.warranty) : "گارانتی ثبت نشده"}</span>
          </div>
          <div class="seller-tags">${providers.length ? creditTags(providers) : '<span class="faint">خرید اقساطی ثبت نشده</span>'}</div>
        </div>
        <div class="seller-side">
          <div class="seller-price">${o.price_toman ? `${faNum(o.price_toman)} <small>تومان</small>` : '<small>قیمت ثبت نشده</small>'}</div>
          <div class="seller-actions">
            <button type="button" class="btn btn-outline btn-sm" data-action="wayfinding" data-shop="${esc(s.shop_id)}">${ICONS.route} مسیر تا مغازه</button>
            <button type="button" class="btn btn-ghost btn-sm" data-action="dossier" data-shop="${esc(s.shop_id)}" data-offer="${esc(o.offer_id)}" data-product="${esc(product.title)}" data-price="${esc(o.price_toman || 0)}">${ICONS.phone} استعلام</button>
            <button type="button" class="btn-link" data-action="panic" data-product="${esc(product.product_id)}" data-shop="${esc(s.shop_id)}" data-shop-name="${esc(s.name)}">${small(ICONS.alert)} بسته بود؟</button>
          </div>
        </div>
      </div>`;
  }

  filterSellers(hub) {
    this.sellerFilter.hub = hub || null;
    this.renderSellers();
  }

  /* ---------- Modals: wayfinding, dossier, panic ---------- */

  openModal(title, bodyHtml) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    const modal = document.getElementById("modal");
    modal.hidden = false;
    modal.querySelector(".modal-head .icon-btn").focus();
  }

  closeModal() {
    document.getElementById("modal").hidden = true;
  }

  async showWayfinding(shopId) {
    this.openModal("مسیر تا مغازه", `<div class="skeleton" style="height:120px"></div>`);
    try {
      const data = await getJSON(`/api/wayfinding/${encodeURIComponent(shopId)}`);
      const n = data.navigation;
      const h = data.hours;
      document.getElementById("modal-title").textContent = `مسیر تا ${data.shop_name}`;
      document.getElementById("modal-body").innerHTML = `
        <div class="seller-loc" style="margin-bottom:8px">${locationLine(n)}</div>
        <p class="muted" style="font-size:12px;margin:0 0 12px">${n.raw_address ? esc(n.raw_address) : "آدرس متنی ثبت نشده"}</p>
        <ol class="steps">${(n.verbal_guide || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        <div class="hours-box">
          <div class="seller-sub" style="margin:0 0 6px">${hoursHtml(h)}</div>
          ${h && h.known ? `<dl class="week-hours">${h.week.map((d) => `<div><dt>${esc(d.day)}</dt><dd>${esc(d.hours)}</dd></div>`).join("")}</dl>` : ""}
        </div>
        <p class="faint" style="font-size:12px;margin:8px 0 0">طبقه و واحد از متن آدرس ثبت‌شده در ترب استخراج شده‌اند؛ پیش از رفتن با فروشگاه تماس بگیرید.</p>`;
    } catch (e) {
      document.getElementById("modal-body").innerHTML = this.errorHtml();
    }
  }

  async showDossier(shopId, productTitle, price, offerId) {
    this.activeShopId = shopId;
    this.openModal("استعلام موجودی پیش از رفتن", `<div class="skeleton" style="height:160px"></div>`);
    // فقط با شناسه آفر؛ آفرهای صفحه کالای قبلی نباید برای یک توقف سبد استفاده شوند
    const offer = offerId ? (this.currentOffers || []).find((o) => o.offer_id === offerId) : null;
    let dossier = offer && offer.dossier;
    const shopName = offer ? offer.shop.name : "";
    try {
      if (!dossier) {
        const params = new URLSearchParams({ product_title: productTitle, shop_name: shopName || "فروشگاه", shop_id: shopId });
        if (price) params.set("price_toman", String(price));
        dossier = await getJSON(`/api/inquiry/dossier?${params}`);
      }
    } catch (e) {
      document.getElementById("modal-body").innerHTML = this.errorHtml();
      return;
    }
    const phone = dossier.phone_number;
    const questions = [["availability", "موجودی و قیمت"], ["warranty", "گارانتی و اصالت"], ["credit", "خرید اقساطی"], ["hours", "ساعت کاری"], ["reserve", "رزرو"]];
    document.getElementById("modal-body").innerHTML = `
      ${shopName ? `<div class="seller-name" style="margin-bottom:4px">${esc(shopName)}</div>` : ""}
      ${offerId ? `
      <div class="sandbox">
        <div class="sandbox-head">
          <strong>${small(ICONS.chat)} شبیه‌ساز استعلام</strong>
          <span class="tag tag-amber">شبیه‌سازی</span>
        </div>
        <p class="sandbox-note">ایجنت کَلَم سؤال را از فروشنده می‌پرسد؛ پاسخ فقط از داده‌های ثبت‌شده همین آفر در ترب ساخته می‌شود و با فروشنده واقعی تماس گرفته نمی‌شود.</p>
        <div class="sandbox-log" id="sandbox-log" aria-live="polite"></div>
        <div class="sandbox-questions">
          ${questions.map(([k, l]) => `<button type="button" class="chip" data-action="simulate" data-offer="${esc(offerId)}" data-question="${k}">${esc(l)}</button>`).join("")}
        </div>
      </div>` : ""}
      <div class="field-label">متن پیشنهادی تماس (حدود ۱۲ ثانیه)</div>
      <div class="script-box" id="phone-script">${esc(dossier.phone_script_12s)}</div>
      <div class="field-label">پیام رزرو برای پیام‌رسان</div>
      <div class="script-box" id="chat-draft" style="white-space:pre-line;font-size:13px">${esc(dossier.chat_draft_text)}</div>
      <div class="hero-actions">
        ${phone
          ? `<a class="btn btn-primary" href="tel:${esc(phone)}">${ICONS.phone} تماس با ${esc(phone)}</a>`
          : `<span class="tag tag-amber" style="line-height:28px">شماره تماسی برای این فروشگاه ثبت نشده</span>`}
        <button type="button" class="btn btn-ghost" data-action="copy" data-target="chat-draft">${ICONS.copy} کپی پیام</button>
      </div>
      ${phone ? `<p class="faint" style="font-size:12px;margin:10px 0 0">شماره‌های تماس در دیتاست آزمایشی ترب ساختگی‌اند و ممکن است به فروشگاه واقعی وصل نشوند.</p>` : ""}`;
  }

  async runSimulation(offerId, question) {
    const log = document.getElementById("sandbox-log");
    if (!log) return;
    try {
      const r = await postJSON("/api/inquiry/simulate", { offer_id: offerId, question });
      const levelCls = { high: "tag-green", medium: "tag-amber", low: "tag-red" }[r.level] || "tag-gray";
      log.insertAdjacentHTML("beforeend", `
        <div class="sb-msg sb-agent"><span class="sb-who">ایجنت کَلَم</span>${esc(r.agent)}</div>
        <div class="sb-msg sb-seller"><span class="sb-who">فروشنده (شبیه‌سازی)</span>${esc(r.seller)}</div>
        <div class="sb-verdict"><span class="tag ${levelCls}">${esc(r.verdict)}</span></div>`);
      log.scrollTop = log.scrollHeight;
    } catch (e) {
      this.toast("شبیه‌سازی انجام نشد.", "error");
    }
  }

  async showPanic(productId, shopId, shopName) {
    this.activeShopId = shopId;
    this.openModal("جایگزین فوری", `<div class="skeleton" style="height:160px"></div>`);
    try {
      const data = await postJSON("/api/fallback/panic", { product_id: productId, failed_shop_id: shopId });
      if (data.error) throw new Error(data.error);
      const list = data.recommended_fallbacks || [];
      const tierClass = { 1: "tag-green", 2: "tag-amber", 3: "tag-gray" };
      document.getElementById("modal-body").innerHTML = `
        <p class="muted" style="margin:0 0 8px;font-size:13px">«${esc(shopName || data.failed_shop.name)}» بسته بود یا کالا را نداشت؟ ${esc(data.action_guide)}</p>
        ${list.length ? list.map((f) => `
          <div class="fallback-row">
            <div style="min-width:0">
              <div class="seller-name">${esc(f.name)} <span class="tag ${tierClass[f.tier] || "tag-gray"}">${esc(f.tier_badge)}</span></div>
              <div class="seller-loc">${locationLine(f.parsed_address)}</div>
              <div class="seller-sub">${hoursHtml(f.hours)}${f.distance_km !== null && f.tier === 3 ? `<span>حدود ${faNum(f.distance_km)} کیلومتر</span>` : ""}</div>
            </div>
            <div class="seller-side">
              <div class="seller-price">${faNum(f.price_toman)} <small>تومان</small></div>
              <button type="button" class="btn btn-outline btn-sm" data-action="wayfinding" data-shop="${esc(f.shop_id)}">${ICONS.route} مسیر</button>
            </div>
          </div>`).join("")
        : `<div class="empty">${ICONS.store}<strong>جایگزینی پیدا نشد</strong><div>فروشگاه دیگری این کالا را با قیمت ثبت‌شده ندارد.</div></div>`}`;
    } catch (e) {
      document.getElementById("modal-body").innerHTML = this.errorHtml();
    }
  }

  async copyText(targetId) {
    const el = document.getElementById(targetId);
    if (!el) return;
    try {
      await navigator.clipboard.writeText(el.textContent);
      this.toast("متن کپی شد.", "success");
    } catch (e) {
      this.toast("کپی انجام نشد؛ متن را دستی انتخاب کنید.", "error");
    }
  }

  /* ---------- Cart & route ---------- */

  saveCart() {
    writeStore(LS_CART, this.cart);
    this.updateCartBadge();
  }

  updateCartBadge() {
    const badge = document.getElementById("cart-count");
    badge.textContent = faNum(this.cart.length);
    badge.hidden = this.cart.length === 0;
  }

  addToCart(id) {
    if (this.cart.some((c) => c.id === id)) return this.toast("این کالا در سبد شماست.");
    const info = this.productCache[id] || { id, title: "", price: 0, image: null };
    this.cart.push({ id, title: info.title, price: info.price, image: info.image });
    this.saveCart();
    this.toast("به سبد خرید حضوری اضافه شد.", "success");
    if (location.hash.startsWith("#/product/")) this.route();
  }

  removeFromCart(id) {
    this.cart = this.cart.filter((c) => c.id !== id);
    this.saveCart();
    this.renderCart();
  }

  async renderCart() {
    if (!this.cart.length) {
      this.setView(`
        <div class="container" style="padding-top:24px">
          <div class="panel empty">${ICONS.cart}<strong>سبد خرید حضوری خالی است</strong>
            <div>کالاهایی را که می‌خواهید حضوری بخرید اضافه کنید تا کَلَم بهترین مسیر بین مغازه‌ها را پیشنهاد دهد.</div>
            <div style="margin-top:16px"><a class="btn btn-primary" href="#/">جستجوی کالا</a></div>
          </div>
        </div>`, "سبد خرید حضوری");
      return;
    }

    this.setView(`
      <div class="container">
        <nav class="breadcrumb" aria-label="مسیر صفحه"><a href="#/">کَلَم</a><span>/</span><span>سبد خرید حضوری</span></nav>
        <div class="cart-layout">
          <div>
            <section class="panel">
              <div class="panel-head">
                <h2>سبد خرید حضوری <span class="faint" style="font-weight:400;font-size:13px">(${faNum(this.cart.length)} کالا)</span></h2>
                <button type="button" class="btn-link" data-action="clear-cart">${ICONS.trash.replace("<svg", '<svg style="width:15px;height:15px"')} حذف همه</button>
              </div>
              ${this.cart.map((c) => `
                <div class="cart-item">
                  ${thumbHtml(c.image, c.title)}
                  <div class="cart-item-title"><a href="#/product/${encodeURIComponent(c.id)}">${esc(c.title || `کالای ${c.id}`)}</a></div>
                  <button type="button" class="icon-btn" data-action="remove-cart" data-id="${esc(c.id)}" aria-label="حذف از سبد">${ICONS.trash}</button>
                </div>`).join("")}
            </section>
            <section class="panel" style="margin-top:16px" id="route-panel">
              <div class="panel-head"><h2>برنامه حرکت</h2><span class="faint" style="font-size:12px" id="route-meta"></span></div>
              <div id="route-body"><div class="panel-body"><div class="skeleton" style="height:140px"></div></div></div>
            </section>
            <section class="panel" style="margin-top:16px">
              <div class="panel-head"><h2>چک‌لیست تحویل پای پیشخوان</h2></div>
              <div class="panel-body">
                <ul class="checklist">
                  <li><label><input type="checkbox"><span><strong>استعلام اصالت در سامانه همتا</strong><small>برای گوشی، سریال (IMEI) روی جعبه و دستگاه را مطابقت دهید.</small></span></label></li>
                  <li><label><input type="checkbox"><span><strong>بررسی پلمپ و سلامت بدنه</strong><small>برچسب گارانتی و نبود آثار باز شدن جعبه را ببینید.</small></span></label></li>
                  <li><label><input type="checkbox"><span><strong>فاکتور با مهر فروشگاه</strong><small>شماره سریال، مدت گارانتی و نشانی فروشگاه در فاکتور باشد.</small></span></label></li>
                  <li><label><input type="checkbox"><span><strong>پایانه اقساطی</strong><small>اگر قسطی می‌خرید، پیش از خرید از فعال بودن کارتخوان اقساطی مطمئن شوید.</small></span></label></li>
                </ul>
              </div>
            </section>
          </div>
          <aside class="panel cart-summary" id="cart-summary">
            <div class="panel-body">
              <div class="segmented" role="tablist" aria-label="روش خرید">
                ${Object.entries(STRATEGIES).map(([k, v]) => `<button type="button" role="tab" aria-selected="${this.strategy === k}" class="${this.strategy === k ? "active" : ""}" data-action="strategy" data-strategy="${k}">${v.label}</button>`).join("")}
              </div>
              <p class="strategy-hint">${esc(STRATEGIES[this.strategy].hint)}</p>
              <div id="summary-body" style="margin-top:12px"><div class="skeleton" style="height:120px"></div></div>
            </div>
          </aside>
        </div>
      </div>`, "سبد خرید حضوری");

    const seq = ++this.renderSeq;
    let data;
    let fromCache = false;
    const ids = this.cart.map((c) => c.id);
    try {
      data = await postJSON("/api/cart/route", { product_ids: ids, preferred_hub: this.hub, strategy: this.strategy });
      writeStore(LS_ROUTE, { ids, strategy: this.strategy, data });
    } catch (e) {
      const cached = readStore(LS_ROUTE, null);
      if (cached && cached.strategy === this.strategy && JSON.stringify(cached.ids) === JSON.stringify(ids)) {
        data = cached.data;
        fromCache = true;
      }
    }
    if (this.isStale(seq) || !document.getElementById("route-body")) return;
    if (!data) {
      document.getElementById("route-body").innerHTML = this.errorHtml();
      document.getElementById("summary-body").innerHTML = "";
      return;
    }
    if (fromCache) this.toast("اتصال قطع است؛ آخرین مسیر ذخیره‌شده نمایش داده شد.");
    this.renderRoute(data);
  }

  renderRoute(data) {
    const route = data.primary_route;
    const body = document.getElementById("route-body");
    const summary = document.getElementById("summary-body");
    const strategyMissing =
      (this.strategy === "single_stop" && !data.single_stop_available) ||
      (this.strategy === "same_hub" && !(data.available_hubs || []).length);

    if (!route || !route.stops || !route.stops.length) {
      body.innerHTML = `<div class="empty">${ICONS.route}<strong>مسیری پیدا نشد</strong><div>برای همه اقلام سبد، فروشگاه حضوری با قیمت ثبت‌شده پیدا نشد.</div></div>`;
      summary.innerHTML = "";
      return;
    }

    const stops = route.stops;
    document.getElementById("route-meta").textContent = route.hub ? `${route.hub}` : "";
    body.innerHTML = `
      ${strategyMissing ? `<div class="panel-body" style="padding-bottom:0"><div class="heavy-note">${this.strategy === "single_stop" ? "هیچ فروشگاهی همه اقلام سبد را با هم ندارد" : "هیچ مرکز خریدی همه اقلام سبد را ندارد"}؛ بهترین مسیر جایگزین نمایش داده شده است.</div></div>` : ""}
      <ol class="timeline">
        ${stops.map((st) => this.stopHtml(st)).join("")}
      </ol>`;

    const best = (data.available_hubs || [])[0];
    const single = data.best_single_stop;
    const lines = [
      ["تعداد مغازه", `${faNum(route.stops_count || stops.length)} مغازه`],
    ];
    if (route.walking_meters) lines.push(["پیاده‌روی تقریبی", `${faNum(route.walking_meters)} متر`]);
    if (route.time_estimate_minutes) lines.push(["زمان تقریبی", `${faNum(route.time_estimate_minutes)} دقیقه`]);

    const compare = [];
    if (best) compare.push([`یک پاساژ (${best.hub})`, best.total_price]);
    if (single) compare.push([`یک مغازه (${single.shop_name})`, single.total_price]);

    summary.innerHTML = `
      <ul class="summary-lines">
        ${lines.map(([k, v]) => `<li><span>${esc(k)}</span><strong>${esc(v)}</strong></li>`).join("")}
      </ul>
      <div class="summary-total"><span>جمع سبد</span><strong>${faNum(route.total_price)} <small style="font-size:12px;font-weight:400">تومان</small></strong></div>
      ${data.savings && this.strategy === "same_hub" ? `<div class="savings-note">${ICONS.tag}<span>${faNum(data.savings.diff_toman)} تومان (${faNum(data.savings.percent)}٪) ارزان‌تر از خرید همه اقلام از یک مغازه</span></div>` : ""}
      ${compare.length ? `
        <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--divider)">
          <div class="field-label" style="margin-bottom:4px">مقایسه</div>
          <ul class="compare-list">${compare.map(([k, v]) => `<li><span>${esc(k)}</span><strong>${faNum(v)} تومان</strong></li>`).join("")}</ul>
        </div>` : ""}
      <button type="button" class="btn btn-ghost btn-block" style="margin-top:14px" data-action="save-route">${ICONS.save} ذخیره مسیر برای حالت بدون اینترنت</button>`;
  }

  stopHtml(st) {
    const pa = st.parsed_address || {};
    const firstItem = (st.items || [])[0];
    return `
      <li class="stop">
        <span class="stop-num">${faNum(st.step_number)}</span>
        <div class="stop-card">
          <div class="stop-top">
            <div>
              <div class="seller-name">${esc(st.shop_name)} ${creditTags(parsePayment(st.payment_options))}</div>
              <div class="seller-loc">${locationLine(pa)}</div>
              <div class="seller-sub">${hoursHtml(st.hours)}</div>
            </div>
          </div>
          ${st.hours && st.hours.state === "closed" ? `<div class="heavy-note closed-note">این مغازه طبق ساعت کاری ثبت‌شده الان بسته است؛ پیش از رفتن تماس بگیرید یا جایگزین را ببینید.</div>` : ""}
          <div class="stop-items">
            ${(st.items || []).map((it) => `
              <div class="stop-item">
                <span>${it.is_heavy ? '<span class="tag tag-amber">سنگین</span> ' : ""}${esc(it.title)}</span>
                <strong>${faNum(it.price)} تومان</strong>
              </div>`).join("")}
          </div>
          ${(pa.verbal_guide || []).length ? `<ol class="stop-guide">${pa.verbal_guide.map((g) => `<li>${esc(g)}</li>`).join("")}</ol>` : ""}
          ${st.has_heavy_item ? `<div class="heavy-note">این توقف کالای سنگین دارد و به آخر مسیر منتقل شده تا بار را در طول خرید حمل نکنید.</div>` : ""}
          <div class="stop-actions">
            ${firstItem ? `<button type="button" class="btn btn-ghost btn-sm" data-action="dossier" data-shop="${esc(st.shop_id)}" data-offer="${esc(firstItem.offer_id || "")}" data-product="${esc(firstItem.title)}" data-price="${esc(firstItem.price)}">${ICONS.phone} استعلام</button>` : ""}
            ${firstItem ? `<button type="button" class="btn-link" data-action="panic" data-product="${esc(firstItem.product_id)}" data-shop="${esc(st.shop_id)}" data-shop-name="${esc(st.shop_name)}">${ICONS.alert.replace("<svg", '<svg style="width:14px;height:14px"')} مغازه بسته بود؟</button>` : ""}
          </div>
        </div>
      </li>`;
  }

  saveRouteOffline() {
    const cached = readStore(LS_ROUTE, null);
    this.toast(cached ? "مسیر در حافظه دستگاه ذخیره شد و بدون اینترنت هم نمایش داده می‌شود." : "مسیری برای ذخیره وجود ندارد.", cached ? "success" : "error");
  }

  /* ---------- About ---------- */

  renderAbout() {
    const algos = [
      ["IP-CRP", "مسیریاب سبد چندقلمی", "انتخاب مغازه‌ها برای خرید چند کالا در یک مرکز خرید، با بالا رفتن یک‌طرفه از طبقات و تحویل کالای سنگین در توقف آخر."],
      ["PACO", "کالاهای مکمل", "پیشنهاد لوازم مکمل (کاور، شارژر، اتصالات) با در نظر گرفتن فاصله مغازه، تازگی قیمت و تناسب قیمت."],
      ["IMWP", "آدرس طبقه و واحد", "استخراج نام پاساژ، طبقه و شماره واحد از متن آدرس و ساخت راهنمای قدم‌به‌قدم."],
      ["CrediPay", "خرید اقساطی حضوری", "نمایش فروشگاه‌هایی که اسنپ‌پی، ترب‌پی، تارا یا دیجی‌پی را با کارتخوان حضوری می‌پذیرند."],
      ["INDP", "غربال نیاز مبهم", "دو سؤال کوتاه برای خریدار مردد (مثلاً کفش یا گوشی) تا جستجو دقیق شود."],
      ["SVDP", "استعلام پیش از رفتن", "تخمین احتمال معتبر بودن قیمت بر اساس تاریخ به‌روزرسانی و متن آماده تماس با فروشگاه."],
      ["TFRA", "جایگزین مغازه بسته", "پیدا کردن فروشگاه جایگزین در همان طبقه، همان پاساژ یا راسته دیگر."],
    ];
    this.setView(`
      <div class="container">
        <nav class="breadcrumb" aria-label="مسیر صفحه"><a href="#/">کَلَم</a><span>/</span><span>درباره کَلَم</span></nav>
        <section class="panel">
          <div class="panel-head">
            <h2>کَلَم چطور کار می‌کند؟</h2>
            <a class="btn btn-outline btn-sm" href="./WHITEPAPER_KALAM.pdf" target="_blank" rel="noopener">دانلود وایت‌پیپر (PDF)</a>
          </div>
          <div class="panel-body">
            <p class="muted" style="margin-top:0">کَلَم خرید حضوری در پاساژها را لایه‌به‌لایه ساده می‌کند: انتخاب مرکز خرید، مسیر بین طبقات، استعلام از فروشگاه و در آخر تحویل کالا یا پیدا کردن جایگزین.</p>
            <div class="algo-grid">
              ${algos.map(([code, title, text]) => `<div class="algo-card"><span class="tag tag-red">${esc(code)}</span><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`).join("")}
            </div>
          </div>
        </section>
      </div>`, "درباره کَلَم");
  }

  /* ---------- Assistant ---------- */

  toggleAssistant(force) {
    const panel = document.getElementById("assistant");
    const fab = document.getElementById("assistant-fab");
    const open = force === undefined ? panel.hidden : force;
    panel.hidden = !open;
    fab.setAttribute("aria-expanded", String(open));
    if (open) {
      if (!document.getElementById("chat-messages").children.length) this.greet();
      document.getElementById("chat-input").focus();
    }
  }

  greet() {
    this.appendMsg("bot", "سلام! من کَلَم هستم. کالا، محدوده، بودجه و شرط قسطی را در یک جمله بگویید (مثلاً «گوشی A55 قسطی در چارسو تا ۲۵ میلیون»)؛ ارزان‌ترین مغازه حضوری، طبقه، واحد و ساعت کاری‌اش را پیدا می‌کنم. سؤال بعدی‌تان («ارزون‌ترش؟») روی همان جستجو اعمال می‌شود.");
  }

  clearChat() {
    document.getElementById("chat-messages").innerHTML = "";
    this.chatState = null;
    this.tree = null;
    this.greet();
  }

  renderChatPrompts() {
    document.getElementById("chat-prompts").innerHTML = CHAT_PROMPTS
      .map((t) => `<button type="button" class="chip" data-action="chat-prompt" data-text="${esc(t)}">${esc(t)}</button>`).join("");
  }

  appendMsg(role, text, extraHtml = "") {
    const box = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = `msg msg-${role}`;
    // متن پیام همیشه ایمن‌سازی می‌شود؛ فقط **پررنگ** پشتیبانی می‌شود
    const safe = esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
    div.innerHTML = `${safe ? `<div>${safe}</div>` : ""}${extraHtml ? `<div class="msg-extra">${extraHtml}</div>` : ""}`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
  }

  async sendChat(text, tree = null) {
    if (document.getElementById("assistant").hidden) this.toggleAssistant(true);
    this.appendMsg("user", text);
    const loading = this.appendMsg("bot", "در حال بررسی فروشگاه‌ها…");
    loading.classList.add("msg-loading");
    try {
      const data = await postJSON("/api/chat", {
        message: tree ? "" : text,
        tree,
        state: this.chatState,
        cart_product_ids: this.cart.map((c) => c.id),
        current_hub: this.hub,
        active_product_id: this.activeProductId,
        active_shop_id: this.activeShopId,
      });
      loading.remove();
      // حافظه گفتگو: وضعیت جستجو برای پیام بعدی («ارزون‌ترش کدومه؟») نگه داشته می‌شود
      if (data.state !== undefined) this.chatState = data.state;
      this.renderBotResponse(data);
    } catch (e) {
      loading.remove();
      this.appendMsg("bot", "ارتباط با سرور برقرار نشد. دوباره تلاش کنید.");
    }
  }

  // درخت نیاز مبهم سمت کلاینت طی می‌شود (مرحله کاربرد، سپس بودجه) و در پایان به صورت ساختاریافته
  // فرستاده می‌شود؛ پس متن پاسخ دوباره درخت را فعال نمی‌کند.
  treeStepHtml(stepIndex) {
    const t = this.tree;
    const step = t.steps[stepIndex];
    return `<strong style="font-size:12px">${esc(step.question)}</strong>` + step.options.map((o, i) =>
      `<button type="button" class="btn btn-ghost msg-option" data-action="tree-option" data-step="${stepIndex}" data-index="${i}">${esc(o.label)}</button>`).join("");
  }

  answerTree(stepIndex, optionIndex) {
    const t = this.tree;
    if (!t) return;
    const label = t.steps[stepIndex].options[optionIndex].label;
    if (stepIndex === 0) {
      t.option_index = optionIndex;
      this.appendMsg("user", label);
      if (t.steps.length > 1) {
        this.appendMsg("bot", "", this.treeStepHtml(1));
        return;
      }
      this.sendTree(null);
    } else {
      this.sendTree(optionIndex, label);
    }
  }

  sendTree(budgetIndex, label) {
    const t = this.tree;
    this.tree = null;
    this.sendChat(label || "همین", { category_key: t.category_key, option_index: t.option_index, budget_index: budgetIndex });
  }

  renderBotResponse(data) {
    let extra = "";
    if (data.type === "diagnostic_tree" && data.diagnostic) {
      this.tree = { category_key: data.category_key, steps: data.diagnostic.steps, option_index: null };
      extra = this.treeStepHtml(0);
    } else if (data.type === "panic_fallback" && data.fallback_data) {
      const fb = data.fallback_data;
      extra = (fb.recommended_fallbacks || []).map((f) => `
        <div class="msg-card">
          <div><strong>${esc(f.name)}</strong><span class="faint">${esc(f.tier_badge)} · ${esc(f.parsed_address.floor_label)} · ${esc(f.hours ? f.hours.label : "")}</span></div>
          <strong style="white-space:nowrap">${faNum(f.price_toman)} ت</strong>
        </div>`).join("") || `<span class="faint">جایگزینی پیدا نشد.</span>`;
    } else if (data.type === "cart_route") {
      extra = `<a class="btn btn-primary btn-sm" href="#/cart" data-action="close-assistant">${ICONS.route} مشاهده برنامه حرکت</a>`;
    } else if ((data.type === "credit_shops" || data.type === "open_shops") && data.shops) {
      extra = data.shops.map((s) => `
        <div class="msg-card">
          <div>
            <strong>${esc(s.name)}</strong>
            <span class="faint">${esc(s.hub || "")} · ${esc(s.parsed_address.floor_label)} · ${esc(s.hours || "")}</span>
            ${s.credit_analysis ? `<span class="msg-tags">${creditTags(s.credit_analysis.badges || [])}</span>` : ""}
          </div>
          <button type="button" class="btn btn-ghost btn-sm" data-action="wayfinding" data-shop="${esc(s.shop_id)}">مسیر</button>
        </div>`).join("");
    } else if (data.type === "product_search" && data.products) {
      data.products.forEach((p) => { this.productCache[p.product_id] = { id: p.product_id, title: p.title, price: p.min_price, image: null }; });
      extra = data.products.slice(0, 4).map((p) => {
        const b = p.best_shop;
        return `
        <div class="msg-card">
          <div>
            <strong><a href="#/product/${encodeURIComponent(p.product_id)}">${esc(p.title)}</a></strong>
            <span class="faint">${b ? `${faNum(b.price)} تومان · ${esc(b.name)} · ${esc(b.parsed_address.mall_name)}، ${esc(b.parsed_address.floor_label)}` : "قیمت نامشخص"}</span>
            ${b ? `<span class="faint">${esc(b.hours)} · ${faNum(p.offline_shops_count)} فروشگاه</span>` : ""}
          </div>
          <button type="button" class="btn btn-outline btn-sm" data-action="add-cart" data-id="${esc(p.product_id)}">افزودن</button>
        </div>`;
      }).join("");
    }
    const source = data.nlu === "claude" ? "درک پیام: Claude" : data.nlu === "local" ? "درک پیام: پارسر محلی" : "";
    if (source && data.type !== "text") extra += `<span class="msg-source">${source}</span>`;
    this.appendMsg("bot", data.message || "", extra);
  }

  /* ---------- Toast ---------- */

  toast(message, type = "") {
    const stack = document.getElementById("toast-stack");
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.textContent = message;
    stack.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.app = new KalamApp();
});
