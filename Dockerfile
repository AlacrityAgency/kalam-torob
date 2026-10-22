FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend backend
COPY public public
COPY scripts scripts
COPY dataset dataset

RUN useradd --create-home kalam \
    && mkdir -p /data \
    && chown -R kalam:kalam /app /data
USER kalam

# پایگاه داده روی دیسک دائمی (/data) ساخته می‌شود تا با هر دیپلوی دوباره ساخته نشود
ENV KALAM_DB_PATH=/data/torob.db \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"

CMD ["sh", "scripts/start.sh"]
