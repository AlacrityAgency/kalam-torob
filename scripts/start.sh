#!/bin/sh
# اجرای کَلَم در کانتینر: اگر پایگاه داده نیست، از یکی از منابع زیر ساخته می‌شود و بعد سرور بالا می‌آید.
#   1) DATASET_ZIP_PATH  مسیر zip دیتاست روی دیسک (مثلاً دیسک لیارا /data/dataset.zip)
#   2) DATASET_ZIP_URL   لینک دانلود مستقیم zip دیتاست
#   3) CSVهای پوشه dataset/ داخل ایمیج
#   4) در غیر این صورت داده نمونه (ساختگی) تا برنامه بالا بیاید؛ رابط کاربری بنر «داده نمونه» نشان می‌دهد
# KALAM_REBUILD_DB=1 پایگاه داده را دوباره می‌سازد.
set -e

export KALAM_DB_PATH="${KALAM_DB_PATH:-/data/torob.db}"
mkdir -p "$(dirname "$KALAM_DB_PATH")"

if [ ! -f "$KALAM_DB_PATH" ] || [ "$KALAM_REBUILD_DB" = "1" ]; then
  if [ -n "$DATASET_ZIP_PATH" ] && [ -f "$DATASET_ZIP_PATH" ]; then
    python scripts/build_db.py "$DATASET_ZIP_PATH"
  elif [ -n "$DATASET_ZIP_URL" ]; then
    echo "Downloading dataset..."
    python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$DATASET_ZIP_URL" /tmp/dataset.zip
    python scripts/build_db.py /tmp/dataset.zip
    rm -f /tmp/dataset.zip
  elif [ -f dataset/shops.csv ]; then
    python scripts/build_db.py
  else
    echo "No dataset provided; building SAMPLE data. Set DATASET_ZIP_PATH or DATASET_ZIP_URL for real data."
    python scripts/generate_sample_dataset.py
    python scripts/build_db.py
  fi
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --proxy-headers
