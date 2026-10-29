# DocuLens API image (Render free web service, or any container host).
FROM python:3.12-slim

# Build args mirror runtime settings: hosts like Render pass service env vars as build args.
# On 512 MB hosts set DISABLE_NEURAL_EMBEDDINGS=1 and LAB_USE_WORDNET=0 (TF-IDF matching, rule-based lemmas).
ARG DISABLE_NEURAL_EMBEDDINGS=0
ARG LAB_USE_WORDNET=1

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HOME=/home/app \
    DOCULENS_DATA_DIR=/home/app/data \
    NLTK_DATA=/home/app/nltk_data \
    FASTEMBED_CACHE_PATH=/home/app/models \
    HF_HUB_DISABLE_TELEMETRY=1 \
    DISABLE_NEURAL_EMBEDDINGS=${DISABLE_NEURAL_EMBEDDINGS} \
    LAB_USE_WORDNET=${LAB_USE_WORDNET} \
    PORT=10000

RUN useradd --create-home --uid 1000 app
WORKDIR /home/app/backend

COPY --chown=app:app requirements.txt .
RUN pip install -r requirements.txt

USER app
# Bake NLTK data (and the embedding model when enabled) into the image so cold starts need no downloads.
RUN python -c "import nltk, os; pkgs = ['punkt_tab', 'stopwords', 'averaged_perceptron_tagger_eng'] + (['wordnet'] if os.environ['LAB_USE_WORDNET'] not in ('0', 'false') else []); [nltk.download(p, quiet=True, download_dir='/home/app/nltk_data') for p in pkgs]" \
 && if [ "$DISABLE_NEURAL_EMBEDDINGS" != "1" ]; then python -c "from fastembed import TextEmbedding; list(TextEmbedding('BAAI/bge-small-en-v1.5').embed(['warm up']))"; fi \
 && mkdir -p /home/app/data

COPY --chown=app:app . .

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"10000\")}/api/health', timeout=4)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
