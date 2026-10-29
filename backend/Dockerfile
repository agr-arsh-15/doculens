# DocuLens API image for Hugging Face Spaces (Docker SDK) or any container host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HOME=/home/app \
    DOCULENS_DATA_DIR=/home/app/data \
    NLTK_DATA=/home/app/nltk_data \
    FASTEMBED_CACHE_PATH=/home/app/models \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PORT=7860

RUN useradd --create-home --uid 1000 app
WORKDIR /home/app/backend

COPY --chown=app:app requirements.txt .
RUN pip install -r requirements.txt

USER app
# Bake NLTK data and the embedding model into the image so cold starts need no downloads.
RUN python -c "import nltk; [nltk.download(p, quiet=True, download_dir='/home/app/nltk_data') for p in ('punkt_tab','stopwords','wordnet','averaged_perceptron_tagger_eng')]" \
 && python -c "from fastembed import TextEmbedding; list(TextEmbedding('BAAI/bge-small-en-v1.5').embed(['warm up']))" \
 && mkdir -p /home/app/data

COPY --chown=app:app . .

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/api/health', timeout=4)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
