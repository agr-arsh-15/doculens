import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DOCULENS_DATA_DIR", BASE_DIR / "data"))
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "doculens.db"
PLAYBOOKS_DIR = Path(__file__).resolve().parent / "playbooks"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)

# LLM provider: "groq" | "gemini" | "openai" | "none". Auto-selects the first provider with a key when unset.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
# Comma-separated models tried when the main model is rate-limited. Unset = provider default; empty = none.
_fallbacks = os.getenv("LLM_FALLBACK_MODELS")
LLM_FALLBACK_MODELS = None if _fallbacks is None else [m.strip() for m in _fallbacks.split(",") if m.strip()]
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_BATCHES = int(os.getenv("LLM_MAX_BATCHES", "5"))
LLM_BATCH_CHARS = int(os.getenv("LLM_BATCH_CHARS", "9000"))
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low").strip().lower()
LLM_CONCURRENCY = max(1, int(os.getenv("LLM_CONCURRENCY", "2")))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
DISABLE_NEURAL_EMBEDDINGS = os.getenv("DISABLE_NEURAL_EMBEDDINGS", "").lower() in {"1", "true", "yes"}

MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "15"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "120"))
MAX_CHARS = int(os.getenv("MAX_CHARS", "400000"))

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

PROMPT_VERSION = "2026.10.1"

DISCLAIMER = (
    "DocuLens provides automated risk analysis for informational purposes only. "
    "It is not legal advice. Consult a qualified professional before acting on any finding."
)

# Stop-word fallback used by the NLP Lab when NLTK corpora are unavailable.
FALLBACK_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him",
    "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't",
    "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "herein", "thereof", "whereas", "hereby", "thereto", "shall",
    "forth", "said", "such"
}
