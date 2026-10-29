"""Verify the configured LLM key with one tiny call: python -m app.llm.check"""
import sys
import time

from app import config
from app.llm.provider import LLMError, get_provider


def main() -> int:
    provider = get_provider()
    if provider is None:
        print("No LLM configured: set GROQ_API_KEY (and LLM_PROVIDER=groq) in the project .env file.")
        return 1
    print(f"Provider: {provider.name}  model: {provider.model}")
    started = time.perf_counter()
    try:
        reply = provider.chat_json('Respond with JSON only: {"ok": true}', "Health check.", max_tokens=400)
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    print(f"OK in {(time.perf_counter() - started) * 1000:.0f} ms, reply: {reply}")
    for key, value in sorted((provider.last_rate_limits or {}).items()):
        print(f"  x-ratelimit-{key}: {value}")
    print(f"Batching: {config.LLM_MAX_BATCHES} x {config.LLM_BATCH_CHARS} chars, "
          f"{config.LLM_MAX_OUTPUT_TOKENS} output tokens, concurrency {config.LLM_CONCURRENCY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
