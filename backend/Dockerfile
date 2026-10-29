FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DOCULENS_DATA_DIR=/data HOST=0.0.0.0 RELOAD=0

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -c "import nltk; [nltk.download(p, quiet=True) for p in ('punkt_tab','stopwords','wordnet','averaged_perceptron_tagger_eng')]" \
    && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" || true

COPY . .
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
