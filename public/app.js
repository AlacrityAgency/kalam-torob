/**
 * کَلَم (Kalam) - سیستم هوشمند خرید حضوری ترب
 * Frontend Interactive Controller & Algorithmic Dashboard
 */

class KalamApp {
  constructor() {
    this.apiBase = "";
    this.currentHub = "چارسو";
    this.currentStrategy = "same_hub";
    this.isOffline = false;
    
    // شناسه‌های اولیه نمونه برای سبد خرید
    this.cartProductIds = [];
    this.cartProductsCache = {};
    
    this.activeProductId = null;
    this.activeShopId = null;

    this.initElements();
    this.attachEventListeners();
    this.bootstrapApp();
  }

  initElements() {
    // Navigation
    this.tabs = document.querySelectorAll(".tab-btn");
    this.views = document.querySelectorAll(".tab-content-view");
    this.hubSelector = document.getElementById("hub-selector");
    this.offlineBtn = document.getElementById("offline-mode-btn");
    this.offlineLabel = document.getElementById("offline-label");
    this.cartPillBtn = document.getElementById("cart-pill-btn");
    this.headerCartCount = document.getElementById("header-cart-count");
    this.brandHomeBtn = document.getElementById("brand-home-btn");

    // Chat
    this.chatMessages = document.getElementById("chat-messages");
    this.chatInput = document.getElementById("chat-input");
    this.chatSendBtn = document.getElementById("chat-send-btn");
    this.clearChatBtn = document.getElementById("clear-chat-btn");

    // Cart Router
    this.cartItemsList = document.getElementById("cart-items-list");
    this.cartItemsCounterBadge = document.getElementById("cart-items-counter-badge");
    this.btnRecomputeRoute = document.getElementById("btn-recompute-route");
    this.btnLoadSamplePreset = document.getElementById("btn-load-sample-preset");
    this.btnLoadIndustrialPreset = document.getElementById("btn-load-industrial-preset");
    this.btnSaveOfflineRoute = document.getElementById("btn-save-offline-route");
    this.itineraryTimeline = document.getElementById("itinerary-timeline");
    this.savingsBanner = document.getElementById("savings-banner");
    this.savingsTitle = document.getElementById("savings-title");
    this.savingsDesc = document.getElementById("savings-desc");
    this.routeSummaryStats = document.getElementById("route-summary-stats");

    // Market Explorer
    this.searchInput = document.getElementById("search-input");
    this.searchBtn = document.getElementById("search-btn");
    this.productsGrid = document.getElementById("products-grid");
    this.catChips = document.querySelectorAll(".cat-chip");

    // Dossier
    this.phoneScriptText = document.getElementById("phone-script-text");
    this.btnTriggerCall = document.getElementById("btn-trigger-call");
    this.btnCopyChatDraft = document.getElementById("btn-copy-chat-draft");

    // Panic
    this.panicFloatingBtn = document.getElementById("panic-floating-btn");
    this.panicModal = document.getElementById("panic-modal");
    this.panicFallbacksList = document.getElementById("panic-fallbacks-list");
    this.panicModalSubtitle = document.getElementById("panic-modal-subtitle");

    // Modals
    this.productModal = document.getElementById("product-modal");
    this.productModalContent = document.getElementById("product-modal-content");
    this.indpModal = document.getElementById("indp-modal");
    this.indpModalContent = document.getElementById("indp-modal-content");
    this.toastContainer = document.getElementById("toast-container");
  }

  attachEventListeners() {
    // Tabs Navigation
    this.tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const targetView = tab.getAttribute("data-tab");
        this.switchTab(targetView);
      });
    });

    this.brandHomeBtn.addEventListener("click", () => this.switchTab("tab-chat"));
    this.cartPillBtn.addEventListener("click", () => this.switchTab("tab-cart"));

    // Hub Selector
    this.hubSelector.addEventListener("change", (e) => {
      this.currentHub = e.target.value;
      this.showToast(`مرکز خرید به «${this.currentHub}» تغییر یافت.`, "info");
      this.recomputeRoute();
    });

    // Offline Mode Toggle
    this.offlineBtn.addEventListener("click", () => this.toggleOfflineMode());

    // Chat
    this.chatSendBtn.addEventListener("click", () => this.sendChatMessage());
    this.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.sendChatMessage();
    });
    this.clearChatBtn.addEventListener("click", () => {
      this.chatMessages.innerHTML = "";
      this.renderBotGreeting();
    });

    // Quick Prompt Buttons
    document.querySelectorAll(".quick-prompt-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const prompt = btn.getAttribute("data-prompt");
        this.chatInput.value = prompt;
        this.sendChatMessage();
      });
    });

    // Cart Router Buttons
    this.btnRecomputeRoute.addEventListener("click", () => this.recomputeRoute());
    this.btnLoadSamplePreset.addEventListener("click", () => this.loadDigitalPreset());
    this.btnLoadIndustrialPreset.addEventListener("click", () => this.loadIndustrialPreset());
    this.btnSaveOfflineRoute.addEventListener("click", () => this.saveCurrentRouteOffline());

    // Market Search
    this.searchBtn.addEventListener("click", () => this.performSearch());
    this.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.performSearch();
    });

    this.catChips.forEach(chip => {
      chip.addEventListener("click", () => {
        this.catChips.forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        const cat = chip.getAttribute("data-cat");
        this.searchInput.value = cat;
        this.performSearch(cat);
      });
    });

    // Dossier Actions
    this.btnTriggerCall.addEventListener("click", () => {
      this.showToast("📞 در حال برقراری تماس با فروشگاه پای پیشخوان...", "success");
    });
    this.btnCopyChatDraft.addEventListener("click", () => {
      const text = this.phoneScriptText.innerText;
      navigator.clipboard.writeText(text);
      this.showToast("متن رزرو با موفقیت کپی شد!", "success");
    });

    // Panic Floating Button
    this.panicFloatingBtn.addEventListener("click", () => this.openPanicModal());
  }

  async bootstrapApp() {
    this.renderBotGreeting();
    await this.loadInitialProducts();
    await this.loadDigitalPreset();
  }

  switchTab(tabId) {
    this.tabs.forEach(tab => {
      tab.classList.toggle("active", tab.getAttribute("data-tab") === tabId);
    });

    const targetViewId = tabId.replace("tab-", "view-");
    this.views.forEach(view => {
      view.style.display = (view.id === targetViewId) ? "block" : "none";
    });

    // هماهنگی ویجت پوست‌کندن لایه‌های کَلَم (Kalam Layer Stepper)
    let stepNum = 3;
    if (tabId === "tab-market") stepNum = 1;
    else if (tabId === "tab-cart") stepNum = 2;
    else if (tabId === "tab-chat") stepNum = 3;
    else if (tabId === "tab-dossier") stepNum = 4;
    else if (tabId === "tab-whitepaper") stepNum = 0;

    this.updateActiveLayerCard(stepNum);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  activateLayer(stepNum) {
    if (stepNum === 1) {
      this.switchTab("tab-market");
      const hubSelect = document.getElementById("hub-selector");
      if (hubSelect) hubSelect.focus();
      this.showToast("لایه ۱: قطب تجاری و ویترین محصولات بازار فعال شد.", "info");
    } else if (stepNum === 2) {
      this.switchTab("tab-cart");
      this.showToast("لایه ۲: مسیریابی سه‌بعدی و چینش طبقات پاساژ فعال شد.", "info");
    } else if (stepNum === 3) {
      this.switchTab("tab-chat");
      this.showToast("لایه ۳: گفتگوی هوشمند، پلاک واحد و استعلام فعال شد.", "info");
    } else if (stepNum === 4) {
      this.switchTab("tab-dossier");
      this.showToast("لایه ۴: چک‌لیست تحویل، استعلام صوتی و دکمه نجات فعال شد.", "info");
    }
  }

  updateActiveLayerCard(stepNum) {
    document.querySelectorAll(".layer-step-card").forEach(card => {
      const cardStep = parseInt(card.getAttribute("data-step"), 10);
      if (stepNum === 0) {
        card.classList.remove("active");
      } else {
        card.classList.toggle("active", cardStep === stepNum);
      }
    });
  }

  toggleOfflineMode() {
    this.isOffline = !this.isOffline;
    this.offlineBtn.classList.toggle("active", this.isOffline);
    if (this.isOffline) {
      this.offlineLabel.innerText = "حالت آفلاین فعال 🟢";
      this.showToast("حالت آفلاین پاساژ فعال شد. داده‌ها از کش محلی خوانده می‌شوند.", "success");
      // ذخیره در LocalStorage
      localStorage.setItem("kalam_offline_mode", "true");
    } else {
      this.offlineLabel.innerText = "حالت آنلاین";
      this.showToast("اتصال زنده به سرور و دیتابیس تورب برقرار شد.", "info");
      localStorage.removeItem("kalam_offline_mode");
    }
  }

  // ================= Chat System =================

  renderBotGreeting() {
    this.appendAssistantMessage(`
سلام! من **کَلَم** هستم، دستیار هوشمند خرید حضوری ترب 🛍️

من برای این طراحی شدم که در شلوغی پاساژها و بازارهای تهران، بهترین مسیر رو براتون بچینم:
* 🗺️ **مسیریابی سبد خرید چندقلمی** با کمترین جابه‌جایی طبقات (الگوریتم IP-CRP)
* 📞 **اسکریپت ۱۲ ثانیه‌ای تماس و استعلام قیمت** قبل از خروج از منزل (SVDP)
* 🚨 **دکمه پنیک:** اگر مغازه بسته بود، فوراً آلترناتیوهای همون طبقه رو براتون پیدا می‌کنم (TFRA)
* 💳 **تفکیک فروشگاه‌های دارای ترمینال اقساطی** اسنپ‌پی و ترب‌پی (CrediPay)

از چی می‌خواین شروع کنیم؟ می‌تونید نیازتون رو بنویسید یا از دکمه‌های راهنمای سمت چپ استفاده کنید.
    `);
  }

  appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message-row user";
    div.innerHTML = `
      <div class="message-avatar user-av">👤</div>
      <div class="message-bubble">${this.escapeHtml(text)}</div>
    `;
    this.chatMessages.appendChild(div);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  appendAssistantMessage(markdownText, extraHtml = "") {
    const div = document.createElement("div");
    div.className = "message-row assistant";
    div.innerHTML = `
      <div class="message-avatar bot-av">🌱</div>
      <div class="message-bubble">
        <div>${this.parseMarkdown(markdownText)}</div>
        ${extraHtml}
      </div>
    `;
    this.chatMessages.appendChild(div);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  async sendChatMessage() {
    const text = this.chatInput.value.trim();
    if (!text) return;

    this.appendUserMessage(text);
    this.chatInput.value = "";

    // نمایش وضعیت انتظار
    const loadingDiv = document.createElement("div");
    loadingDiv.className = "message-row assistant";
    loadingDiv.id = "chat-loading-indicator";
    loadingDiv.innerHTML = `
      <div class="message-avatar bot-av">🌱</div>
      <div class="message-bubble" style="color: var(--text-muted);">کَلَم در حال تحلیل داده‌ها و تطبیق الگوریتم‌های بازار...</div>
    `;
    this.chatMessages.appendChild(loadingDiv);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;

    try {
      const res = await fetch(`${this.apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          cart_product_ids: this.cartProductIds,
          current_hub: this.currentHub,
          active_product_id: this.activeProductId,
          active_shop_id: this.activeShopId
        })
      });
      const data = await res.json();
      loadingDiv.remove();
      this.renderBotResponse(data);
    } catch (err) {
      loadingDiv.remove();
      this.appendAssistantMessage("متأسفانه ارتباط با سرور برقرار نشد. لطفاً مجدداً امتحان کنید.");
    }
  }

  renderBotResponse(data) {
    let extraHtml = "";

    // ۱. اگر درخت تشخیصی INDP باشد
    if (data.type === "diagnostic_tree") {
      const step1 = data.diagnostic.steps[0];
      extraHtml += `
        <div style="margin-top: 1rem; background: rgba(0,0,0,0.3); border-radius: var(--radius-md); padding: 1rem; border: 1px solid var(--border-subtle);">
          <div style="font-weight: 700; margin-bottom: 0.75rem; color: var(--accent-cyan);">${step1.question}</div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            ${step1.options.map(opt => `
              <button class="chip-btn" style="text-align: right; justify-content: flex-start; padding: 0.6rem 1rem;"
                onclick="app.handleIndpSelection('${opt.query_tag}')">
                ${opt.label}
              </button>
            `).join("")}
          </div>
        </div>
      `;
    }

    // ۲. اگر دکمه پنیک اضطراری باشد
    if (data.type === "panic_fallback") {
      const fb = data.fallback_data;
      extraHtml += `
        <div style="margin-top: 1rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: var(--radius-md); padding: 1rem;">
          <div style="color: #f87171; font-weight: 800; margin-bottom: 0.5rem;">🚨 نجات فوری در همان مرکز خرید:</div>
          <div style="font-size: 0.85rem; margin-bottom: 0.75rem;">${fb.action_guide}</div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            ${(fb.recommended_fallbacks || []).map(item => `
              <div style="background: rgba(0,0,0,0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <strong>${item.name}</strong>
                  <div style="font-size: 0.75rem; color: var(--accent-cyan);">${item.parsed_address.floor_label} • ${item.parsed_address.unit_number}</div>
                </div>
                <div style="text-align: left;">
                  <span class="tier-badge tier-${item.tier}">${item.tier_badge}</span>
                  <div style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; margin-top: 2px;">${item.price_toman.toLocaleString('fa-IR')} ت</div>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }

    // ۳. اگر مسیر سبد خرید باشد
    if (data.type === "cart_route") {
      extraHtml += `
        <div style="margin-top: 1rem;">
          <button class="btn-primary-sm" onclick="app.switchTab('tab-cart')">
            🗺️ مشاهده کامل مسیر خرید در نقشه پاساژ
          </button>
        </div>
      `;
    }

    // ۴. کارت‌های محصول
    if (data.type === "product_search" && data.products) {
      extraHtml += `
        <div style="display: grid; grid-template-columns: 1fr; gap: 0.65rem; margin-top: 1rem;">
          ${data.products.slice(0, 3).map(p => `
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 0.9rem;">${p.title}</strong>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
                  ${p.offline_shops_count} مغازه در تهران • بهترین قیمت: ${(p.min_price || 0).toLocaleString('fa-IR')} تومان
                </div>
              </div>
              <button class="btn-primary-sm" style="padding: 0.35rem 0.75rem;" onclick="app.addCartItem('${p.product_id}', '${p.title.replace(/'/g, "")}', ${p.min_price || 0})">
                + افزودن به سبد
              </button>
            </div>
          `).join("")}
        </div>
      `;
    }

    // پیام اصلی را درج کن
    this.appendAssistantMessage(data.message, extraHtml);
  }

  handleIndpSelection(queryTag) {
    this.chatInput.value = `دنبال ${queryTag} هستم و بودجه مناسب مدنظرمه`;
    this.sendChatMessage();
  }

  // ================= Cart Router (IP-CRP) =================

  async loadDigitalPreset() {
    // نمونه محبوب سبد چندقلمی دیجیتال در پاساژ پایتخت / چارسو
    // استخراج ۳ محصول محبوب لپ‌تاپ، ماوس و هدفون
    try {
      const res = await fetch(`${this.apiBase}/api/search?q=ایسوس&limit=1`);
      const d1 = await res.json();
      const res2 = await fetch(`${this.apiBase}/api/search?q=ماوس&limit=1`);
      const d2 = await res2.json();
      const res3 = await fetch(`${this.apiBase}/api/search?q=ایرپاد&limit=1`);
      const d3 = await res3.json();

      this.cartProductIds = [];
      if (d1.products && d1.products[0]) this.cartProductIds.push(d1.products[0].product_id);
      if (d2.products && d2.products[0]) this.cartProductIds.push(d2.products[0].product_id);
      if (d3.products && d3.products[0]) this.cartProductIds.push(d3.products[0].product_id);

      this.currentHub = "پایتخت";
      this.hubSelector.value = "پایتخت";
      await this.recomputeRoute();
      this.showToast("سبد نمونه دیجیتال در پاساژ پایتخت بارگذاری شد.", "success");
    } catch (e) {
      console.error(e);
    }
  }

  async loadIndustrialPreset() {
    // سبد نمونه کارگاهی برای اثبات قید Heavy-Item در لاله‌زار
    try {
      const res1 = await fetch(`${this.apiBase}/api/search?q=موتور برق&limit=1`);
      const d1 = await res1.json();
      const res2 = await fetch(`${this.apiBase}/api/search?q=کابل برق&limit=1`);
      const d2 = await res2.json();
      const res3 = await fetch(`${this.apiBase}/api/search?q=دریل&limit=1`);
      const d3 = await res3.json();

      this.cartProductIds = [];
      if (d1.products && d1.products[0]) this.cartProductIds.push(d1.products[0].product_id);
      if (d2.products && d2.products[0]) this.cartProductIds.push(d2.products[0].product_id);
      if (d3.products && d3.products[0]) this.cartProductIds.push(d3.products[0].product_id);

      this.currentHub = "لاله زار";
      this.hubSelector.value = "لاله زار";
      await this.recomputeRoute();
      this.showToast("سبد نمونه صنعتی با قید کالای سنگین در لاله‌زار بارگذاری شد.", "success");
    } catch (e) {
      console.error(e);
    }
  }

  addCartItem(productId, title, price) {
    if (!this.cartProductIds.includes(productId)) {
      this.cartProductIds.push(productId);
      this.cartProductsCache[productId] = { title, price };
      this.updateCartCountUI();
      this.showToast(`«${title.slice(0, 25)}...» به سبد خرید اضافه شد.`, "success");
      this.recomputeRoute();
    } else {
      this.showToast("این کالا در سبد خرید شما وجود دارد.", "info");
    }
  }

  removeCartItem(productId) {
    this.cartProductIds = this.cartProductIds.filter(id => id !== productId);
    delete this.cartProductsCache[productId];
    this.updateCartCountUI();
    this.recomputeRoute();
    this.showToast("کالا از سبد حذف شد.", "info");
  }

  updateCartCountUI() {
    const count = this.cartProductIds.length;
    this.headerCartCount.innerText = count;
    this.cartItemsCounterBadge.innerText = `${count} کالا`;
  }

  selectStrategy(stratKey) {
    this.currentStrategy = stratKey;
    document.querySelectorAll(".strategy-card").forEach(c => c.classList.remove("active"));
    const activeCard = document.getElementById(`strat-${stratKey.replace("_", "-")}`);
    if (activeCard) activeCard.classList.add("active");
    this.recomputeRoute();
  }

  async recomputeRoute() {
    this.updateCartCountUI();

    if (this.cartProductIds.length === 0) {
      this.cartItemsList.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem;">سبد خرید خالی است. از بخش جستجو کالا اضافه کنید.</div>`;
      this.itineraryTimeline.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem;">مسیری برای نمایش وجود ندارد.</div>`;
      return;
    }

    // بررسی حالت آفلاین در زیرزمین و پارکینگ
    if (this.isOffline) {
      const cached = localStorage.getItem("kalam_saved_route_data");
      if (cached) {
        try {
          const data = JSON.parse(cached);
          this.renderCartItemsList(data);
          this.renderRouteOutput(data);
          this.showToast("📡 در حال استفاده از نقشه کش‌شده آفلاین در حافظه دستگاه", "info");
          return;
        } catch (e) {}
      }
    }

    try {
      const res = await fetch(`${this.apiBase}/api/cart/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_ids: this.cartProductIds,
          preferred_hub: this.currentHub,
          strategy: this.currentStrategy
        })
      });
      const data = await res.json();
      // ذخیره در حافظه پایدار آفلاین مرورگر
      localStorage.setItem("kalam_saved_route_data", JSON.stringify(data));
      this.renderCartItemsList(data);
      this.renderRouteOutput(data);
    } catch (err) {
      console.warn("خطا در شبکه، تلاش برای بازیابی از کش محلی:", err);
      const cached = localStorage.getItem("kalam_saved_route_data");
      if (cached) {
        const data = JSON.parse(cached);
        this.renderCartItemsList(data);
        this.renderRouteOutput(data);
        this.showToast("📡 شبکه در دسترس نیست. مسیر از کش محلی بازیابی شد.", "warning");
      } else {
        this.showToast("خطا در محاسبه مسیر سبد خرید.", "error");
      }
    }
  }

  renderCartItemsList(routeData) {
    this.cartItemsList.innerHTML = this.cartProductIds.map(pid => {
      const p = this.cartProductsCache[pid] || { title: `کالای کد ${pid.slice(0, 8)}`, price: 0 };
      return `
        <div class="cart-item-row">
          <div class="cart-item-title" title="${p.title}">${p.title}</div>
          <button class="remove-cart-item" onclick="app.removeCartItem('${pid}')" title="حذف کالا">✕</button>
        </div>
      `;
    }).join("");
  }

  renderRouteOutput(data) {
    const primary = data.primary_route;
    const savings = data.savings;

    // به‌روزرسانی کارت‌های استراتژی
    const sameHubCard = document.getElementById("strat-same-hub-price");
    const sameHubStops = document.getElementById("strat-same-hub-stops");
    const sameHubTime = document.getElementById("strat-same-hub-time");
    const singleStopCard = document.getElementById("strat-single-stop-price");
    const bargainCard = document.getElementById("strat-bargain-price");

    if (data.available_hubs && data.available_hubs.length > 0) {
      const h0 = data.available_hubs[0];
      sameHubCard.innerText = `${h0.total_price.toLocaleString('fa-IR')} تومان`;
      sameHubStops.innerText = `${h0.stops_count} مغازه`;
      sameHubTime.innerText = `${h0.time_estimate_minutes} دقیقه`;
    }

    if (data.best_single_stop) {
      singleStopCard.innerText = `${data.best_single_stop.total_price.toLocaleString('fa-IR')} تومان`;
    } else {
      singleStopCard.innerText = "ناموجود در تک‌فروشگاه";
    }

    bargainCard.innerText = primary ? `${(primary.total_price * 0.96).toFixed(0).toLocaleString('fa-IR')} تومان` : "-";

    // بنر صرفه‌جویی
    if (savings) {
      this.savingsBanner.style.display = "flex";
      this.savingsTitle.innerText = `💰 ${savings.diff_toman.toLocaleString('fa-IR')} تومان (${savings.percent}٪) صرفه‌جویی در خرید حضوری!`;
      this.savingsDesc.innerText = savings.description;
    } else {
      this.savingsBanner.style.display = "none";
    }

    if (!primary || !primary.stops) {
      this.itineraryTimeline.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem;">هیچ توقفی برای این استراتژی در دسترس نیست.</div>`;
      return;
    }

    this.routeSummaryStats.innerText = `${primary.stops.length} توقف • ${primary.walking_meters || 90} متر پیاده‌روی • تخمین زمان: ${primary.time_estimate_minutes || 25} دقیقه`;

    // رندر تایم‌لاین گام‌به‌گام
    this.itineraryTimeline.innerHTML = primary.stops.map(stop => {
      const pAddr = stop.parsed_address;
      const isHeavy = stop.has_heavy_item;

      return `
        <div class="itinerary-step-card">
          <div class="step-number-col">
            <div class="step-circle">${stop.step_number}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${pAddr.floor_label}</div>
          </div>

          <div class="step-details">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <div>
                <div class="step-shop-name">${stop.shop_name}</div>
                <div class="step-mall-location">
                  <span>🏢 ${pAddr.mall_name}</span> • 
                  <span>📍 ${pAddr.floor_label}</span> • 
                  <span>🚪 ${pAddr.unit_number}</span>
                </div>
              </div>
              <button class="btn-outline-sm" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.4);"
                onclick="app.triggerShopPanic('${stop.shop_id}', '${stop.shop_name}')">
                🚨 مغازه بسته بود؟
              </button>
            </div>

            <!-- راهنمای کلامی ۳ مرحله‌ای IMWP -->
            <div class="step-verbal-guide">
              <strong>راهنمای کلامی حرکت پای پیاده:</strong>
              <div style="margin-top: 0.25rem;">
                ${(pAddr.verbal_guide || []).map((step, i) => `<div>${i + 1}. ${step}</div>`).join("")}
              </div>
            </div>

            <!-- اقلام تحویلی در این توقف -->
            <div class="step-items-list">
              ${(stop.items || []).map(it => `
                <div class="step-item-tag ${it.is_heavy ? 'heavy-item-tag' : ''}">
                  <span>${it.is_heavy ? '📦 کالای سنگین:' : '🛍️'}</span>
                  <strong>${it.title}</strong>
                  <span style="color: var(--accent-cyan); font-weight: 700;">${it.price.toLocaleString('fa-IR')} ت</span>
                </div>
              `).join("")}
            </div>

            ${isHeavy ? `
              <div style="margin-top: 0.65rem; font-size: 0.75rem; color: var(--accent-amber); display: flex; align-items: center; gap: 0.35rem;">
                ⚠️ <strong>قید کالای سنگین کَلَم اعمال شد:</strong> این اقلام در آخرین توقف تحویل گرفته می‌شوند تا در حین خرید سنگینی بار را حمل نکنید.
              </div>
            ` : ''}

            <!-- دکمه‌های اقدام سریع هر توقف -->
            <div style="margin-top: 0.85rem; display: flex; gap: 0.5rem;">
              <button class="btn-outline-sm" onclick="app.showDossierForStop('${stop.shop_name}', '${stop.items[0]?.title || ''}', ${stop.items[0]?.price || 0}, '${stop.shop_id}')">
                📞 استعلام تلفنی ۱۲ ثانیه‌ای (SVDP)
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  saveCurrentRouteOffline() {
    const routeSnapshot = {
      hub: this.currentHub,
      strategy: this.currentStrategy,
      items: this.cartProductIds,
      timestamp: new Date().toISOString()
    };
    localStorage.setItem("kalam_saved_route", JSON.stringify(routeSnapshot));
    this.showToast("✅ کل برنامه حرکت و آدرس واحدهای پاساژ در حافظه آفلاین گوشی ذخیره شد.", "success");
  }

  // ================= Market Explorer =================

  async loadInitialProducts() {
    try {
      const res = await fetch(`${this.apiBase}/api/products/suggested`);
      const data = await res.json();
      this.renderProductsGrid(data.suggested || []);
    } catch (e) {
      console.error(e);
    }
  }

  async performSearch(overrideCat = null) {
    const q = overrideCat || this.searchInput.value.trim();
    if (!q) return;

    this.productsGrid.innerHTML = `<div style="color: var(--text-muted); padding: 2rem;">در حال جستجو در دیتابیس ترب...</div>`;

    try {
      const res = await fetch(`${this.apiBase}/api/search?q=${encodeURIComponent(q)}&hub=${encodeURIComponent(this.currentHub)}&limit=24`);
      const data = await res.json();
      this.renderProductsGrid(data.products || []);
    } catch (e) {
      console.error(e);
      this.showToast("خطا در جستجوی محصولات.", "error");
    }
  }

  renderProductsGrid(products) {
    if (!products || products.length === 0) {
      this.productsGrid.innerHTML = `<div style="color: var(--text-muted); padding: 2rem;">کالایی با این مشخصات در این مرکز خرید یافت نشد.</div>`;
      return;
    }

    this.productsGrid.innerHTML = products.map(p => {
      const priceStr = p.min_price_toman ? `${p.min_price_toman.toLocaleString('fa-IR')} تومان` : "استعلام در محل";
      let imgHtml = "";
      if (p.image_url) {
        try {
          const urls = typeof p.image_url === "string" && p.image_url.startsWith("[") ? JSON.parse(p.image_url) : [p.image_url];
          if (urls && urls[0]) {
            imgHtml = `<img src="${urls[0]}" alt="${this.escapeHtml(p.persian_title)}" style="width: 58px; height: 58px; object-fit: contain; border-radius: var(--radius-sm); background: rgba(255,255,255,0.04); padding: 4px; border: 1px solid var(--border-subtle); flex-shrink: 0;" loading="lazy" onerror="this.style.display='none'">`;
          }
        } catch(e) {}
      }

      return `
        <div class="product-card glass">
          <div>
            <div style="display: flex; gap: 0.85rem; align-items: flex-start; margin-bottom: 0.75rem;">
              ${imgHtml}
              <div style="flex: 1;">
                <span class="strategy-badge" style="position: static; display: inline-block; padding: 0.15rem 0.6rem; font-size: 0.7rem; margin-bottom: 0.35rem;">${p.category_name || 'کالای بازار'}</span>
                <div class="product-title" title="${this.escapeHtml(p.persian_title)}">${p.persian_title}</div>
              </div>
            </div>

            <div class="product-meta">
              <span>🏷️ ${p.brand_name || 'برند متفرقه'}</span>
              <span>🏬 ${p.available_offline_shops_count || 1} مغازه حضوری</span>
            </div>
          </div>

          <div>
            <div class="product-price">${priceStr}</div>
            <div class="product-actions">
              <button class="btn-primary-sm" onclick="app.addCartItem('${p.product_id}', '${p.persian_title.replace(/'/g, "")}', ${p.min_price_toman || 0})">
                + افزودن به مسیر
              </button>
              <button class="btn-outline-sm" onclick="app.showProductDetails('${p.product_id}')">
                جزئیات و مکمل‌ها
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  async showProductDetails(productId) {
    try {
      const [prodRes, compRes] = await Promise.all([
        fetch(`${this.apiBase}/api/product/${productId}`),
        fetch(`${this.apiBase}/api/complementary/${productId}`)
      ]);
      const prodData = await prodRes.json();
      const compData = await compRes.json();

      this.activeProductId = productId;
      const p = prodData.product;
      const offers = prodData.offers || [];
      const comps = compData.recommendations || [];

      this.productModalContent.innerHTML = `
        <h3 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 0.5rem;">${p.title}</h3>
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.25rem;">
          دسته: ${p.category} • برند: ${p.brand} • موجود در ${offers.length} فروشگاه حضوری تهران
        </div>

        <!-- لیست مغازه‌های حضوری -->
        <h4 style="margin-bottom: 0.75rem; color: var(--accent-cyan);">🏬 فروشگاه‌های ارائه‌دهنده در پاساژ:</h4>
        <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 220px; overflow-y: auto; margin-bottom: 1.5rem;">
          ${offers.map(off => `
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem 1rem; border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong>${off.shop.name}</strong>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${off.shop.parsed_address.mall_name} • ${off.shop.parsed_address.floor_label} • ${off.shop.parsed_address.unit_number}</div>
              </div>
              <div style="text-align: left;">
                <div style="color: #38bdf8; font-weight: 800;">${off.price_toman.toLocaleString('fa-IR')} ت</div>
                <div style="font-size: 0.7rem; color: var(--kalam-emerald);">${off.stock_certainty.badge.label}</div>
              </div>
            </div>
          `).join("")}
        </div>

        <!-- کالاهای مکمل پیشنهادی الگوریتم PACO -->
        <h4 style="margin-bottom: 0.75rem; color: var(--kalam-emerald);">🧩 اقلام مکمل ضروری در همین مرکز خرید (الگوریتم PACO):</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          ${comps.map(c => `
            <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); padding: 0.75rem; border-radius: var(--radius-md);">
              <div style="font-size: 0.85rem; font-weight: 700;">${c.title}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">${c.parsed_address.floor_label} (${c.shop_name})</div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                <span style="font-size: 0.8rem; font-weight: 700; color: #34d399;">${c.price_toman.toLocaleString('fa-IR')} ت</span>
                <button class="btn-primary-sm" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
                  onclick="app.addCartItem('${c.product_id}', '${c.title.replace(/'/g, "")}', ${c.price_toman}); app.closeModal('product-modal');">
                  + افزودن
                </button>
              </div>
            </div>
          `).join("")}
        </div>
      `;

      this.openModal("product-modal");
    } catch (e) {
      console.error(e);
      this.showToast("خطا در واکشی جزئیات محصول.", "error");
    }
  }

  // ================= Panic Button (TFRA) =================

  async triggerShopPanic(shopId, shopName) {
    this.activeShopId = shopId;
    const targetProd = this.cartProductIds[0];
    if (!targetProd) {
      this.showToast("ابتدا کالایی را به سبد خرید اضافه کنید.", "warning");
      return;
    }

    try {
      const res = await fetch(`${this.apiBase}/api/fallback/panic`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: targetProd,
          failed_shop_id: shopId
        })
      });
      const data = await res.json();
      this.renderPanicFallbacks(shopName, data);
      this.openModal("panic-modal");
    } catch (e) {
      console.error(e);
      this.showToast("خطا در بازیابی آلترناتیوهای اضطراری.", "error");
    }
  }

  async openPanicModal() {
    // از اولین توقف سبد یا مغازه پیش‌فرض استفاده کن
    const sampleShop = "1";
    await this.triggerShopPanic(sampleShop, "فروشگاه نمونه");
  }

  renderPanicFallbacks(failedShopName, data) {
    this.panicModalSubtitle.innerText = `فروشگاه «${failedShopName}» پاسخگو نبود؟ نگران نباشید! در کمتر از ۱٫۵ ثانیه، مغازه‌های آلترناتیو در همان پاساژ برای شما پیدا شد:`;

    const fallbacks = data.recommended_fallbacks || [];
    if (fallbacks.length === 0) {
      this.panicFallbacksList.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem;">فروشگاه آلترناتیوی با موجودی قطعی در این پاساژ پیدا نشد.</div>`;
      return;
    }

    this.panicFallbacksList.innerHTML = fallbacks.map(fb => `
      <div class="panic-fallback-item">
        <div>
          <div style="font-weight: 800; font-size: 1rem;">${fb.name}</div>
          <div style="font-size: 0.8rem; color: var(--accent-cyan); margin-top: 2px;">
            🏢 ${fb.parsed_address.mall_name} • 📍 ${fb.parsed_address.floor_label} • 🚪 ${fb.parsed_address.unit_number}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
            ${fb.warranty}
          </div>
        </div>

        <div style="text-align: left;">
          <span class="tier-badge tier-${fb.tier}">${fb.tier_badge}</span>
          <div style="font-size: 1.1rem; font-weight: 900; color: #38bdf8; margin: 0.25rem 0;">
            ${fb.price_toman.toLocaleString('fa-IR')} ت
          </div>
          <button class="btn-primary-sm" style="font-size: 0.75rem;" onclick="app.showToast('مسیر شما به این مغازه به‌روز شد!', 'success'); app.closeModal('panic-modal');">
            هدایت به این مغازه ➔
          </button>
        </div>
      </div>
    `).join("");
  }

  // ================= SVDP Voice & Dossier =================

  showDossierForStop(shopName, prodTitle, priceToman, shopId) {
    const formattedPrice = priceToman ? `${priceToman.toLocaleString('fa-IR')} تومان` : "قیمت روز";
    const script = `«سلام وقت بخیر، از سمت ترب تماس می‌گیرم. آیا مدل ${prodTitle.slice(0, 30)} رو موجود دارین و قیمت روزتون همون ${formattedPrice} هست؟ برای خرید حضوری تا چه ساعتی تشریف دارید؟»`;
    this.phoneScriptText.innerText = script;
    this.switchTab("tab-dossier");
  }

  // ================= Modals & Utilities =================

  openModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.add("open");
  }

  closeModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.remove("open");
  }

  showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = "toast";
    const icon = type === "success" ? "✅" : (type === "warning" ? "⚠️" : (type === "error" ? "❌" : "ℹ️"));
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    this.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  parseMarkdown(text) {
    if (!text) return "";
    let html = this.escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Bullet lists
    html = html.replace(/^\* (.*$)/gim, '<li style="margin-right: 1.2rem;">$1</li>');
    // Line breaks
    html = html.replace(/\n/g, '<br/>');
    return html;
  }
}

// مقداردهی اولیه برنامه
let app = null;
window.addEventListener("DOMContentLoaded", () => {
  app = new KalamApp();
  window.app = app;
});
