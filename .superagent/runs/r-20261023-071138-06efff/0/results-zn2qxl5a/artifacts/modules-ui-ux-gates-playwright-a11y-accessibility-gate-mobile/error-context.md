# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: modules/ui-ux/gates/playwright/a11y.spec.js >> accessibility gate
- Location: modules/ui-ux/gates/playwright/a11y.spec.js:46:1

# Error details

```
Error: axe-core WCAG violations

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 4

- Array []
+ Array [
+   "button-name",
+   "color-contrast",
+ ]
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - link "رفتن به محتوای اصلی" [ref=e2] [cursor=pointer]:
    - /url: "#view"
  - banner [ref=e3]:
    - generic [ref=e4]:
      - link "صفحه اصلی کَلَم" [ref=e5] [cursor=pointer]:
        - /url: "#/"
        - generic [ref=e6]:
          - generic [ref=e7]: کَلَم
          - generic [ref=e8]: خرید حضوری ترب
      - generic [ref=e9]:
        - button "همه محدوده‌ها" [ref=e11] [cursor=pointer]
        - button "موقعیت من" [ref=e18] [cursor=pointer]
        - link "سبد خرید حضوری" [ref=e23] [cursor=pointer]:
          - /url: "#/cart"
    - navigation "دسته‌بندی‌ها" [ref=e28]:
      - generic [ref=e29]:
        - link "گوشی موبایل" [ref=e30] [cursor=pointer]:
          - /url: "#/search?q=%DA%AF%D9%88%D8%B4%DB%8C%20%D9%85%D9%88%D8%A8%D8%A7%DB%8C%D9%84"
        - link "لپ‌تاپ" [ref=e31] [cursor=pointer]:
          - /url: "#/search?q=%D9%84%D9%BE%20%D8%AA%D8%A7%D9%BE"
        - link "هدفون و هندزفری" [ref=e32] [cursor=pointer]:
          - /url: "#/search?q=%D9%87%D8%AF%D9%81%D9%88%D9%86"
        - link "ماوس و کیبورد" [ref=e33] [cursor=pointer]:
          - /url: "#/search?q=%D9%85%D8%A7%D9%88%D8%B3"
        - link "شارژر" [ref=e34] [cursor=pointer]:
          - /url: "#/search?q=%D8%B4%D8%A7%D8%B1%DA%98%D8%B1"
        - link "کیف و کاور" [ref=e35] [cursor=pointer]:
          - /url: "#/search?q=%DA%A9%D8%A7%D9%88%D8%B1%20%DA%AF%D9%88%D8%B4%DB%8C"
        - link "ساعت هوشمند" [ref=e36] [cursor=pointer]:
          - /url: "#/search?q=%D8%B3%D8%A7%D8%B9%D8%AA%20%D9%87%D9%88%D8%B4%D9%85%D9%86%D8%AF"
        - link "کفش و کتانی" [ref=e37] [cursor=pointer]:
          - /url: "#/search?q=%DA%A9%D8%AA%D8%A7%D9%86%DB%8C"
        - link "دوربین مداربسته" [ref=e38] [cursor=pointer]:
          - /url: "#/search?q=%D8%AF%D9%88%D8%B1%D8%A8%DB%8C%D9%86%20%D9%85%D8%AF%D8%A7%D8%B1%D8%A8%D8%B3%D8%AA%D9%87"
        - link "سیم و کابل" [ref=e39] [cursor=pointer]:
          - /url: "#/search?q=%DA%A9%D8%A7%D8%A8%D9%84%20%D8%A8%D8%B1%D9%82"
        - link "ابزار برقی" [ref=e40] [cursor=pointer]:
          - /url: "#/search?q=%D8%AF%D8%B1%DB%8C%D9%84"
        - link "پمپ آب" [ref=e41] [cursor=pointer]:
          - /url: "#/search?q=%D9%BE%D9%85%D9%BE%20%D8%A2%D8%A8"
        - link "موتور برق" [ref=e42] [cursor=pointer]:
          - /url: "#/search?q=%D9%85%D9%88%D8%AA%D9%88%D8%B1%20%D8%A8%D8%B1%D9%82"
  - main [ref=e43]:
    - generic [ref=e44]:
      - heading "کَلَم" [level=1] [ref=e45]
      - paragraph [ref=e46]: کمترین قیمت حضوری، آدرس دقیق طبقه و واحد، و مسیر خرید در پاساژهای تهران
      - search [ref=e47]:
        - searchbox "جستجوی کالا" [active] [ref=e48]
        - button "جستجو" [ref=e49] [cursor=pointer]
      - generic [ref=e53]:
        - generic [ref=e54]: "جستجوهای پرطرفدار:"
        - link "ایرپاد" [ref=e55] [cursor=pointer]:
          - /url: "#/search?q=%D8%A7%DB%8C%D8%B1%D9%BE%D8%A7%D8%AF"
        - link "Galaxy A55" [ref=e56] [cursor=pointer]:
          - /url: "#/search?q=Galaxy%20A55"
        - link "لپ تاپ ایسوس" [ref=e57] [cursor=pointer]:
          - /url: "#/search?q=%D9%84%D9%BE%20%D8%AA%D8%A7%D9%BE%20%D8%A7%DB%8C%D8%B3%D9%88%D8%B3"
        - link "ماوس لاجیتک" [ref=e58] [cursor=pointer]:
          - /url: "#/search?q=%D9%85%D8%A7%D9%88%D8%B3%20%D9%84%D8%A7%D8%AC%DB%8C%D8%AA%DA%A9"
        - link "کتونی رانینگ" [ref=e59] [cursor=pointer]:
          - /url: "#/search?q=%DA%A9%D8%AA%D9%88%D9%86%DB%8C%20%D8%B1%D8%A7%D9%86%DB%8C%D9%86%DA%AF"
        - link "دریل شارژی" [ref=e60] [cursor=pointer]:
          - /url: "#/search?q=%D8%AF%D8%B1%DB%8C%D9%84%20%D8%B4%D8%A7%D8%B1%DA%98%DB%8C"
    - generic [ref=e61]:
      - heading "مراکز خرید" [level=2] [ref=e63]
      - generic [ref=e64]:
        - button [ref=e65] [cursor=pointer]:
          - generic [ref=e69]:
            - strong [ref=e70]: فردوسی
            - text: ۱٬۹۶۲ فروشگاه
        - button [ref=e71] [cursor=pointer]:
          - generic [ref=e75]:
            - strong [ref=e76]: شیخ هادی
            - text: ۹۳۶ فروشگاه
        - button [ref=e77] [cursor=pointer]:
          - generic [ref=e81]:
            - strong [ref=e82]: بهارستان
            - text: ۳۶۹ فروشگاه
        - button [ref=e83] [cursor=pointer]:
          - generic [ref=e87]:
            - strong [ref=e88]: آسمان
            - text: ۸۶ فروشگاه
        - button [ref=e89] [cursor=pointer]:
          - generic [ref=e93]:
            - strong [ref=e94]: ایرانشهر
            - text: ۵۹ فروشگاه
        - button [ref=e95] [cursor=pointer]:
          - generic [ref=e99]:
            - strong [ref=e100]: سنائی
            - text: ۵۴ فروشگاه
        - button [ref=e101] [cursor=pointer]:
          - generic [ref=e105]:
            - strong [ref=e106]: باغ فیض
            - text: ۵۳ فروشگاه
        - button [ref=e107] [cursor=pointer]:
          - generic [ref=e111]:
            - strong [ref=e112]: جنت آباد جنوبی
            - text: ۳۹ فروشگاه
        - button [ref=e113] [cursor=pointer]:
          - generic [ref=e117]:
            - strong [ref=e118]: آذربایجان
            - text: ۳۸ فروشگاه
        - button [ref=e119] [cursor=pointer]:
          - generic [ref=e123]:
            - strong [ref=e124]: تجریش
            - text: ۳۸ فروشگاه
        - button [ref=e125] [cursor=pointer]:
          - generic [ref=e129]:
            - strong [ref=e130]: سهروردی
            - text: ۳۶ فروشگاه
        - button [ref=e131] [cursor=pointer]:
          - generic [ref=e135]:
            - strong [ref=e136]: امجدیه
            - text: ۳۳ فروشگاه
        - button [ref=e137] [cursor=pointer]:
          - generic [ref=e141]:
            - strong [ref=e142]: آشتیانی
            - text: ۱۶ فروشگاه
        - button [ref=e143] [cursor=pointer]:
          - generic [ref=e147]:
            - strong [ref=e148]: کیانشهر شمالی
            - text: ۱۱ فروشگاه
        - button [ref=e149] [cursor=pointer]:
          - generic [ref=e153]:
            - strong [ref=e154]: بهار
            - text: ۱۰ فروشگاه
        - button [ref=e155] [cursor=pointer]:
          - generic [ref=e159]:
            - strong [ref=e160]: درختی
            - text: ۷ فروشگاه
        - button [ref=e161] [cursor=pointer]:
          - generic [ref=e165]:
            - strong [ref=e166]: فلسطین
            - text: ۷ فروشگاه
        - button [ref=e167] [cursor=pointer]:
          - generic [ref=e171]:
            - strong [ref=e172]: مطهری
            - text: ۷ فروشگاه
        - button [ref=e173] [cursor=pointer]:
          - generic [ref=e177]:
            - strong [ref=e178]: مهران
            - text: ۶ فروشگاه
        - button [ref=e179] [cursor=pointer]:
          - generic [ref=e183]:
            - strong [ref=e184]: ولیعصر
            - text: ۶ فروشگاه
        - button [ref=e185] [cursor=pointer]:
          - generic [ref=e189]:
            - strong [ref=e190]: سازمان برنامه شمالی
            - text: ۴ فروشگاه
        - button [ref=e191] [cursor=pointer]:
          - generic [ref=e195]:
            - strong [ref=e196]: امام زاده قاسم
            - text: ۳ فروشگاه
        - button [ref=e197] [cursor=pointer]:
          - generic [ref=e201]:
            - strong [ref=e202]: تهران پارس
            - text: ۳ فروشگاه
        - button [ref=e203] [cursor=pointer]:
          - generic [ref=e207]:
            - strong [ref=e208]: باغ فردوس
            - text: ۲ فروشگاه
        - button [ref=e209] [cursor=pointer]:
          - generic [ref=e213]:
            - strong [ref=e214]: دزاشیب
            - text: ۲ فروشگاه
        - button [ref=e215] [cursor=pointer]:
          - generic [ref=e219]:
            - strong [ref=e220]: عباس آباد
            - text: ۲ فروشگاه
      - heading "پرفروشنده‌ترین کالاها در بازار حضوری" [level=2] [ref=e222]
      - generic [ref=e223]:
        - generic [ref=e224]:
          - link "شارژر اپل توان 20 وات سه پین شارژر اپل توان 20 وات سه پین از۱٬۳۰۰٬۰۰۰ تومان در ۵۷ فروشگاه حضوری" [ref=e225] [cursor=pointer]:
            - /url: "#/product/product_df1dfb162403cf73df70fdf3"
            - img "شارژر اپل توان 20 وات سه پین" [ref=e227]
            - heading "شارژر اپل توان 20 وات سه پین" [level=3] [ref=e228]
            - generic [ref=e229]: از۱٬۳۰۰٬۰۰۰ تومان
            - generic [ref=e230]: در ۵۷ فروشگاه حضوری
          - button "+ مقایسه" [ref=e231] [cursor=pointer]
        - generic [ref=e232]:
          - link "سیستم اعلام سرقت سایلکس مدل SG8 LITE سیستم اعلام سرقت سایلکس مدل SG8 LITE از۱۳٬۴۰۰٬۰۰۰ تومان در ۴۸ فروشگاه حضوری" [ref=e233] [cursor=pointer]:
            - /url: "#/product/product_ea14709af5027eb47228dae3"
            - img "سیستم اعلام سرقت سایلکس مدل SG8 LITE" [ref=e235]
            - heading "سیستم اعلام سرقت سایلکس مدل SG8 LITE" [level=3] [ref=e236]
            - generic [ref=e237]: از۱۳٬۴۰۰٬۰۰۰ تومان
            - generic [ref=e238]: در ۴۸ فروشگاه حضوری
          - button "+ مقایسه" [ref=e239] [cursor=pointer]
        - generic [ref=e240]:
          - link "دزدگیر سیم کارتی سایلکس مدل SG8-805S دزدگیر سیم کارتی سایلکس مدل SG8-805S از۱۵٬۴۰۰٬۰۰۰ تومان در ۴۷ فروشگاه حضوری" [ref=e241] [cursor=pointer]:
            - /url: "#/product/product_98c1e1a7d51493c9d1cf80dd"
            - img "دزدگیر سیم کارتی سایلکس مدل SG8-805S" [ref=e243]
            - heading "دزدگیر سیم کارتی سایلکس مدل SG8-805S" [level=3] [ref=e244]
            - generic [ref=e245]: از۱۵٬۴۰۰٬۰۰۰ تومان
            - generic [ref=e246]: در ۴۷ فروشگاه حضوری
          - button "+ مقایسه" [ref=e247] [cursor=pointer]
        - generic [ref=e248]:
          - link "منبع تغذیه سوییچینگ ۱۲ ولت ۳۰ آمپر فن دار منبع تغذیه سوییچینگ ۱۲ ولت ۳۰ آمپر فن دار از۱٬۶۵۰٬۰۰۰ تومان در ۴۴ فروشگاه حضوری" [ref=e249] [cursor=pointer]:
            - /url: "#/product/product_6a0dc6c1b338c9eecef13a73"
            - img "منبع تغذیه سوییچینگ ۱۲ ولت ۳۰ آمپر فن دار" [ref=e251]
            - heading "منبع تغذیه سوییچینگ ۱۲ ولت ۳۰ آمپر فن دار" [level=3] [ref=e252]
            - generic [ref=e253]: از۱٬۶۵۰٬۰۰۰ تومان
            - generic [ref=e254]: در ۴۴ فروشگاه حضوری
          - button "+ مقایسه" [ref=e255] [cursor=pointer]
        - generic [ref=e256]:
          - link "سیم افشان افشار نژاد خراسان سطح مقطع 2.۵ سیم افشان افشار نژاد خراسان سطح مقطع 2.۵ از۵٬۱۰۰٬۰۰۰ تومان در ۴۰ فروشگاه حضوری" [ref=e257] [cursor=pointer]:
            - /url: "#/product/product_9b36205cbdc7ee5304fc85b6"
            - img "سیم افشان افشار نژاد خراسان سطح مقطع 2.۵" [ref=e259]
            - heading "سیم افشان افشار نژاد خراسان سطح مقطع 2.۵" [level=3] [ref=e260]
            - generic [ref=e261]: از۵٬۱۰۰٬۰۰۰ تومان
            - generic [ref=e262]: در ۴۰ فروشگاه حضوری
          - button "+ مقایسه" [ref=e263] [cursor=pointer]
        - generic [ref=e264]:
          - link "دزدگیر اماکن کلاسیک مدل X5 DUPLEX دزدگیر اماکن کلاسیک مدل X5 DUPLEX از۱۳٬۵۰۰٬۰۰۰ تومان در ۳۹ فروشگاه حضوری" [ref=e265] [cursor=pointer]:
            - /url: "#/product/product_419886d8958c69c6d8426d31"
            - img "دزدگیر اماکن کلاسیک مدل X5 DUPLEX" [ref=e267]
            - heading "دزدگیر اماکن کلاسیک مدل X5 DUPLEX" [level=3] [ref=e268]
            - generic [ref=e269]: از۱۳٬۵۰۰٬۰۰۰ تومان
            - generic [ref=e270]: در ۳۹ فروشگاه حضوری
          - button "+ مقایسه" [ref=e271] [cursor=pointer]
        - generic [ref=e272]:
          - link "محافظ برق ۱۶ آمپر پارت الکتریک مناسب کولرگازی و فر محافظ برق ۱۶ آمپر پارت الکتریک مناسب کولرگازی و فر از۸۰۰٬۰۰۰ تومان در ۳۸ فروشگاه حضوری" [ref=e273] [cursor=pointer]:
            - /url: "#/product/product_fb2e8349333c9804bdd2a376"
            - img "محافظ برق ۱۶ آمپر پارت الکتریک مناسب کولرگازی و فر" [ref=e275]
            - heading "محافظ برق ۱۶ آمپر پارت الکتریک مناسب کولرگازی و فر" [level=3] [ref=e276]
            - generic [ref=e277]: از۸۰۰٬۰۰۰ تومان
            - generic [ref=e278]: در ۳۸ فروشگاه حضوری
          - button "+ مقایسه" [ref=e279] [cursor=pointer]
        - generic [ref=e280]:
          - link "اسپیکر بلوتوثی هارمن کاردن مدل Aura Studio 5 اسپیکر بلوتوثی هارمن کاردن مدل Aura Studio 5 از۵۳٬۹۰۰٬۰۰۰ تومان در ۳۷ فروشگاه حضوری" [ref=e281] [cursor=pointer]:
            - /url: "#/product/product_241eb5d0978b4382eddeeddf"
            - img "اسپیکر بلوتوثی هارمن کاردن مدل Aura Studio 5" [ref=e283]
            - heading "اسپیکر بلوتوثی هارمن کاردن مدل Aura Studio 5" [level=3] [ref=e284]
            - generic [ref=e285]: از۵۳٬۹۰۰٬۰۰۰ تومان
            - generic [ref=e286]: در ۳۷ فروشگاه حضوری
          - button "+ مقایسه" [ref=e287] [cursor=pointer]
        - generic [ref=e288]:
          - link "پاورسویچینگ ۱۲ولت ۲۰ آمپر فن دار پاورسویچینگ ۱۲ولت ۲۰ آمپر فن دار از۱٬۴۰۰٬۰۰۰ تومان در ۳۷ فروشگاه حضوری" [ref=e289] [cursor=pointer]:
            - /url: "#/product/product_6c649a06419cac48af836d9b"
            - img "پاورسویچینگ ۱۲ولت ۲۰ آمپر فن دار" [ref=e291]
            - heading "پاورسویچینگ ۱۲ولت ۲۰ آمپر فن دار" [level=3] [ref=e292]
            - generic [ref=e293]: از۱٬۴۰۰٬۰۰۰ تومان
            - generic [ref=e294]: در ۳۷ فروشگاه حضوری
          - button "+ مقایسه" [ref=e295] [cursor=pointer]
        - generic [ref=e296]:
          - link "محافظ یخچال دو خانه ارتدار پارت الکتریک با کابل 1.8 متری محافظ یخچال دو خانه ارتدار پارت الکتریک با کابل 1.8 متری از۸۶۵٬۰۰۰ تومان در ۳۶ فروشگاه حضوری" [ref=e297] [cursor=pointer]:
            - /url: "#/product/product_a112c972266b57d0f7eddeab"
            - img "محافظ یخچال دو خانه ارتدار پارت الکتریک با کابل 1.8 متری" [ref=e299]
            - heading "محافظ یخچال دو خانه ارتدار پارت الکتریک با کابل 1.8 متری" [level=3] [ref=e300]
            - generic [ref=e301]: از۸۶۵٬۰۰۰ تومان
            - generic [ref=e302]: در ۳۶ فروشگاه حضوری
          - button "+ مقایسه" [ref=e303] [cursor=pointer]
        - generic [ref=e304]:
          - link "کنتاکتور اشنایدر مدل LC1D18M7 ظرفیت 18 آمپر 220 ولت کنتاکتور اشنایدر مدل LC1D18M7 ظرفیت 18 آمپر 220 ولت از۱٬۳۵۰٬۰۰۰ تومان در ۳۴ فروشگاه حضوری" [ref=e305] [cursor=pointer]:
            - /url: "#/product/product_491e2d6b7ccb5f48cd7175f4"
            - img "کنتاکتور اشنایدر مدل LC1D18M7 ظرفیت 18 آمپر 220 ولت" [ref=e307]
            - heading "کنتاکتور اشنایدر مدل LC1D18M7 ظرفیت 18 آمپر 220 ولت" [level=3] [ref=e308]
            - generic [ref=e309]: از۱٬۳۵۰٬۰۰۰ تومان
            - generic [ref=e310]: در ۳۴ فروشگاه حضوری
          - button "+ مقایسه" [ref=e311] [cursor=pointer]
        - generic [ref=e312]:
          - link "محافظ ولتاژ جریان تکفاز 63 آمپر JBH محافظ ولتاژ جریان تکفاز 63 آمپر JBH از۱٬۴۵۰٬۰۰۰ تومان در ۳۴ فروشگاه حضوری" [ref=e313] [cursor=pointer]:
            - /url: "#/product/product_5c15a7b70ae1e04999ec0fab"
            - img "محافظ ولتاژ جریان تکفاز 63 آمپر JBH" [ref=e315]
            - heading "محافظ ولتاژ جریان تکفاز 63 آمپر JBH" [level=3] [ref=e316]
            - generic [ref=e317]: از۱٬۴۵۰٬۰۰۰ تومان
            - generic [ref=e318]: در ۳۴ فروشگاه حضوری
          - button "+ مقایسه" [ref=e319] [cursor=pointer]
      - generic [ref=e320]:
        - generic [ref=e326]:
          - strong [ref=e327]: مسیر خرید چندقلمی
          - text: چند کالا را در یک پاساژ با کمترین رفت‌وآمد بین طبقات بخرید.
        - generic [ref=e332]:
          - strong [ref=e333]: آدرس طبقه و واحد
          - text: نام پاساژ، طبقه و شماره واحد هر مغازه، با راهنمای قدم‌به‌قدم.
        - generic [ref=e337]:
          - strong [ref=e338]: استعلام پیش از رفتن
          - text: متن آماده تماس برای پرسیدن موجودی و قیمت روز.
        - generic [ref=e343]:
          - strong [ref=e344]: مغازه بسته بود؟
          - text: نزدیک‌ترین فروشگاه جایگزین در همان طبقه یا همان پاساژ.
  - contentinfo [ref=e345]:
    - generic [ref=e346]:
      - generic [ref=e348]:
        - strong [ref=e349]: کَلَم
        - paragraph [ref=e350]: دستیار خرید حضوری ترب؛ مقایسه قیمت، مسیر خرید و آدرس دقیق مغازه‌ها در پاساژهای تهران.
        - paragraph [ref=e351]: در دیتاست آزمایشی ترب، نام بیشتر فروشگاه‌ها و همه شماره‌های تماس ساختگی‌اند؛ فقط فروشگاه‌های دارای نشان «اینستاگرام» یا «وب‌سایت» هویت آنلاین واقعی دارند.
      - list [ref=e352]:
        - listitem [ref=e353]:
          - link "درباره کَلَم و الگوریتم‌ها" [ref=e354] [cursor=pointer]:
            - /url: "#/about"
        - listitem [ref=e355]:
          - link "وایت‌پیپر (PDF)" [ref=e356] [cursor=pointer]:
            - /url: ./WHITEPAPER_KALAM.pdf
        - listitem [ref=e357]:
          - link "سبد خرید حضوری" [ref=e358] [cursor=pointer]:
            - /url: "#/cart"
  - button [ref=e359] [cursor=pointer]
```

# Test source

```ts
  1  | // @ts-check
  2  | // Accessibility gate spec. Run it through modules/ui-ux/gates/a11y.py, which checks preconditions,
  3  | // sets the environment below and maps results to the PASS/FAIL/NOT-TESTED/ERROR contract.
  4  | //
  5  | // Environment:
  6  | //   TARGET_URL       live page to audit (http(s):// or file://)
  7  | //   SANDBOX_PATH     absolute path to a standalone HTML prototype
  8  | //   A11Y_RESULTS_DIR where per-viewport violation JSON is written
  9  | //   MOUNT_TIMEOUT_MS how long to wait for the sandbox to render (default 15000)
  10 | //   VISUAL_BASELINE  set to 1 to compare against a committed screenshot baseline
  11 | const { test, expect } = require('@playwright/test');
  12 | const AxeBuilder = require('@axe-core/playwright').default;
  13 | const fs = require('fs');
  14 | const path = require('path');
  15 | const { pathToFileURL } = require('url');
  16 | 
  17 | const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
  18 | const MOUNT_SELECTOR = '#root > *, [data-component-root] > *';
  19 | 
  20 | const targetUrl = process.env.TARGET_URL;
  21 | const sandboxPath = process.env.SANDBOX_PATH;
  22 | const resultsDir = process.env.A11Y_RESULTS_DIR;
  23 | const mountTimeout = Number(process.env.MOUNT_TIMEOUT_MS || 15000);
  24 | 
  25 | function writeResults(projectName, payload) {
  26 |   if (!resultsDir) return;
  27 |   fs.mkdirSync(resultsDir, { recursive: true });
  28 |   fs.writeFileSync(path.join(resultsDir, `${projectName}.json`), JSON.stringify(payload, null, 2));
  29 | }
  30 | 
  31 | /** Resolve once the mount root has children, or reject on an uncaught page error or timeout. */
  32 | async function waitForMount(page, pageErrors) {
  33 |   const deadline = Date.now() + mountTimeout;
  34 |   while (Date.now() < deadline) {
  35 |     if (pageErrors.length > 0) {
  36 |       throw new Error(`Sandbox threw before mounting:\n${pageErrors.join('\n')}`);
  37 |     }
  38 |     if ((await page.locator(MOUNT_SELECTOR).count()) > 0) return;
  39 |     await page.waitForTimeout(100);
  40 |   }
  41 |   throw new Error(
  42 |     `Sandbox did not render anything inside #root or [data-component-root] within ${mountTimeout}ms.`
  43 |   );
  44 | }
  45 | 
  46 | test('accessibility gate', async ({ page }, testInfo) => {
  47 |   if (!targetUrl && !sandboxPath) {
  48 |     // Never skip: a skipped gate looks green to anything that only reads the exit code.
  49 |     throw new Error('NOT-TESTED: set TARGET_URL or SANDBOX_PATH (use modules/ui-ux/gates/a11y.py).');
  50 |   }
  51 | 
  52 |   const pageErrors = [];
  53 |   page.on('pageerror', (err) => pageErrors.push(err.message));
  54 | 
  55 |   if (sandboxPath) {
  56 |     await page.goto(pathToFileURL(sandboxPath).href, { waitUntil: 'domcontentloaded' });
  57 |     await waitForMount(page, pageErrors);
  58 |   } else {
  59 |     await page.goto(/** @type {string} */ (targetUrl), { waitUntil: 'load' });
  60 |     // Dev servers with long-lived connections may never go idle; idle is best-effort only.
  61 |     await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  62 |   }
  63 | 
  64 |   const scan = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  65 |   const violations = scan.violations.map((v) => ({
  66 |     id: v.id,
  67 |     impact: v.impact,
  68 |     help: v.help,
  69 |     helpUrl: v.helpUrl,
  70 |     nodes: v.nodes.map((n) => ({ target: n.target.join(' '), failureSummary: n.failureSummary })),
  71 |   }));
  72 | 
  73 |   writeResults(testInfo.project.name, {
  74 |     target: sandboxPath || targetUrl,
  75 |     viewport: page.viewportSize(),
  76 |     violations,
  77 |     pageErrors,
  78 |   });
  79 | 
  80 |   expect(pageErrors, 'uncaught page errors').toEqual([]);
> 81 |   expect(violations.map((v) => v.id), 'axe-core WCAG violations').toEqual([]);
     |                                                                   ^ Error: axe-core WCAG violations
  82 | 
  83 |   if (process.env.VISUAL_BASELINE === '1') {
  84 |     await expect(page).toHaveScreenshot(`${testInfo.project.name}.png`, {
  85 |       maxDiffPixelRatio: 0.02,
  86 |       animations: 'disabled',
  87 |     });
  88 |   }
  89 | });
  90 | 
```