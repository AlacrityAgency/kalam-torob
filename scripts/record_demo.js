// ضبط ویدئوی دمو بی‌صدا با زیرنویس فارسی (۱۲۸۰×۷۲۰، webm)
//   python -m uvicorn backend.main:app --port 8000   # روی پایگاه داده نمونه یا واقعی
//   node scripts/record_demo.js [پوشه خروجی] [آدرس سرور]
//   ffmpeg -i out/*.webm -c:v libx264 -crf 26 -pix_fmt yuv420p docs/demo/kalam-demo.mp4
// شناسه کالاهای 50001 و 50014 مربوط به داده نمونه است؛ برای دیتاست واقعی عوضشان کنید.
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  ({ chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright'));
}
const out = process.argv[2] || 'demo-out';
const CAP = `(t) => { let d = document.getElementById('__cap'); if (!d) { d = document.createElement('div'); d.id='__cap';
  d.style.cssText='position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:99999;background:rgba(20,20,20,.88);color:#fff;font:600 19px Vazirmatn,Tahoma;padding:12px 22px;border-radius:12px;direction:rtl;max-width:88vw;text-align:center;line-height:1.8;box-shadow:0 6px 24px rgba(0,0,0,.3)';
  document.body.appendChild(d);} d.textContent = t; }`;
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: out, size: { width: 1280, height: 720 } },
    geolocation: { latitude: 35.692, longitude: 51.408 }, permissions: ['geolocation'] });
  const page = await ctx.newPage();
  const base = (process.argv[3] || 'http://127.0.0.1:8000').replace(/\/?$/, '/');
  const cap = async (t, ms = 4200) => { await page.evaluate(new Function('return ' + CAP)(), t).catch(() => {}); await page.waitForTimeout(ms); };
  const capAfterNav = async (t, ms) => { await page.waitForTimeout(600); await cap(t, ms); };
  const type = async (sel, text) => { await page.click(sel); await page.type(sel, text, { delay: 55 }); };

  await page.goto(base + '#/'); await capAfterNav('کَلَم: دستیار هوشمند خرید حضوری ترب برای پاساژها و مراکز خرید تهران', 4500);
  await cap('چهار گام: انتخاب کالا ← پیدا کردن فروشگاه‌های نزدیک ← مقایسه ← ارتباط با فروشنده', 4500);

  await page.click('#loc-btn'); await cap('اول موقعیت کاربر را می‌گیریم تا فاصله فروشگاه‌ها محاسبه شود', 3200);
  await page.click('[data-action="loc-gps"]'); await page.waitForTimeout(1200);

  await page.click('#assistant-fab'); await cap('گام ۱: کاربر نمی‌داند چه مدلی بخرد', 2500);
  await type('#chat-input', 'دنبال یه کفش کتونی خوب برای پیاده‌روی هستم'); await page.press('#chat-input', 'Enter');
  await cap('دستیار دو سؤال کوتاه می‌پرسد: کاربرد و بودجه', 3500);
  await page.click('[data-action="tree-option"][data-step="0"][data-index="0"]'); await page.waitForTimeout(1200);
  await page.click('[data-action="tree-option"][data-step="1"][data-index="1"]'); await cap('و کفش‌های مناسب با قیمت، فروشگاه، طبقه و ساعت کاری را پیشنهاد می‌دهد', 4500);
  await type('#chat-input', 'گوشی A55 قسطی در چارسو'); await page.press('#chat-input', 'Enter');
  await cap('کالا، محدوده و شرط اقساط از یک جمله فهمیده می‌شود', 4000);
  await type('#chat-input', 'ارزون‌ترش کدومه؟'); await page.press('#chat-input', 'Enter');
  await cap('حافظه گفتگو: سؤال بعدی روی همان جستجو اعمال می‌شود', 4000);
  await page.click('[data-action="close-assistant"]');

  await page.goto(base + '#/search?q=' + encodeURIComponent('گوشی')); await capAfterNav('همه‌چیز از چت نمی‌گذرد: جستجو با کارت و فیلتر', 3200);
  await page.click('[data-action="search-condition"][data-key="credit"]'); await cap('گام ۲: فیلتر «خرید اقساطی» — فقط فروشگاه‌های دارای اقساط', 3500);
  await page.click('[data-action="sort"][data-sort="nearest"]'); await cap('مرتب‌سازی بر اساس نزدیک‌ترین فروشگاه به کاربر', 3500);
  await page.click('.compare-toggle >> nth=0'); await page.click('.compare-toggle >> nth=1'); await page.click('.compare-toggle >> nth=2');
  await page.goto(base + '#/compare'); await capAfterNav('مقایسه کنار‌هم کالاها: قیمت، تعداد فروشگاه، فاصله، اقساط و مشخصات فنی', 5500);

  await page.goto(base + '#/product/50001'); await capAfterNav('گام ۳: مقایسه فروشگاه‌ها برای یک کالا', 3000);
  await page.evaluate(() => document.getElementById('sellers').scrollIntoView({ behavior: 'smooth' })); await cap('«پیشنهاد کلم» با دلیل: قیمت، فاصله، باز بودن و تازگی قیمت', 5000);
  await page.evaluate(() => window.scrollBy({ top: 420, behavior: 'smooth' })); await cap('هر فروشنده: پاساژ، طبقه، واحد، ساعت کاری، گارانتی و اقساط؛ اطلاعات نامشخص صریح نوشته می‌شود', 5500);
  await page.click('.seller-row [data-action="wayfinding"] >> nth=0'); await cap('آدرس دقیق داخل پاساژ و راهنمای قدم‌به‌قدم', 4500);
  await page.click('.modal-head [data-action="close-modal"]');

  await page.evaluate(() => document.getElementById('sellers').scrollIntoView()); await page.waitForTimeout(400);
  await page.click('.rec-card [data-action="follow-up"]'); await cap('گام ۴: ایجنت پیگیری — ساعت کاری، پاسخ‌گویی، قیمت، گارانتی، اقساط (شبیه‌سازی از داده)', 6500);
  await cap('اگر فروشنده جواب ندهد یا قیمت قابل اتکا نباشد، جایگزین‌ها خودکار پیشنهاد می‌شوند', 4500);
  await page.click('.modal-head [data-action="close-modal"]');
  await page.click('.seller-row [data-action="panic"] >> nth=0'); await cap('مغازه بسته بود؟ جایگزین در همین طبقه، همین پاساژ یا نزدیک‌ترین محدوده', 5000);
  await page.click('.modal-head [data-action="close-modal"]');

  await page.click('.hero-actions [data-action="add-cart"]'); await page.waitForTimeout(800);
  await page.goto(base + '#/product/50014'); await page.waitForTimeout(800); await page.click('.hero-actions [data-action="add-cart"]');
  await page.goto(base + '#/cart'); await capAfterNav('سبد چندقلمی: مسیر خرید در یک پاساژ، طبقات از پایین به بالا', 4500);
  await cap('بهترین زمان مراجعه: زمانی که همه مغازه‌های مسیر باز هستند', 4500);

  await page.goto(base + '#/'); await capAfterNav('کَلَم — فارسی، موبایل‌محور، شفاف و قابل استفاده بدون اینترنت', 4500);
  await ctx.close(); await browser.close();
})();
