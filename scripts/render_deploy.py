"""Set the DocuLens API's environment on Render and trigger a deploy. Values are never printed.

Run from the repository root (the setup wizard does this for you):
  RENDER_API_KEY=... .venv/bin/python scripts/render_deploy.py            # all values from .env.deploy
  RENDER_API_KEY=... .venv/bin/python scripts/render_deploy.py CORS_ORIGINS=https://example.vercel.app

Render's API replaces the whole variable list on update, so existing variables are read first and merged.
Prints API_URL=<service address> on success.
"""
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.render.com/v1"
SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "doculens-api")
FROM_FILE = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL", "GROQ_API_KEY", "ENCRYPTION_KEY",
             "ADMIN_EMAILS", "CORS_ORIGINS"]
DEFAULTS = {"APP_ENV": "production", "AUTH_MODE": "supabase", "SUPABASE_STORAGE_BUCKET": "documents",
            "DISABLE_NEURAL_EMBEDDINGS": "1", "LAB_USE_WORDNET": "0", "ANALYSIS_WORKERS": "1"}


def read_env(path: Path) -> dict:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def main() -> int:
    token = os.environ.get("RENDER_API_KEY")
    if not token:
        print("RENDER_API_KEY is required.", file=sys.stderr)
        return 2
    overrides = dict(arg.split("=", 1) for arg in sys.argv[1:] if "=" in arg)
    client = httpx.Client(base_url=API, timeout=30, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})

    r = client.get("/services", params={"name": SERVICE_NAME, "limit": 20})
    r.raise_for_status()
    matches = [item["service"] for item in r.json() if item["service"]["name"] == SERVICE_NAME]
    if not matches:
        print(f"No Render service named {SERVICE_NAME}. Create it from the Blueprint first.", file=sys.stderr)
        return 1
    service = matches[0]

    current, cursor = {}, None
    while True:
        r = client.get(f"/services/{service['id']}/env-vars", params={"limit": 100, **({"cursor": cursor} if cursor else {})})
        r.raise_for_status()
        page = r.json()
        current.update({item["envVar"]["key"]: item["envVar"]["value"] for item in page})
        if len(page) < 100:
            break
        cursor = page[-1]["cursor"]

    if overrides:
        wanted = {**current, **overrides}
    else:
        values = read_env(ROOT / os.environ.get("ENV_FILE", ".env.deploy"))
        missing = [k for k in FROM_FILE if not values.get(k)]
        if missing:
            print(f"Missing values in .env.deploy: {', '.join(missing)}", file=sys.stderr)
            return 2
        wanted = {**DEFAULTS, **current, **{k: values[k] for k in FROM_FILE}}

    r = client.put(f"/services/{service['id']}/env-vars", json=[{"key": k, "value": v} for k, v in sorted(wanted.items())])
    r.raise_for_status()
    r = client.post(f"/services/{service['id']}/deploys", json={"clearCache": "do_not_clear"})
    r.raise_for_status()
    print(f"Set {len(wanted)} environment variables on {SERVICE_NAME} and started a deploy.")
    print(f"API_URL={service['serviceDetails']['url'].rstrip('/')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.HTTPStatusError as exc:
        print(f"Render API error: HTTP {exc.response.status_code} on {exc.request.url.path}", file=sys.stderr)
        sys.exit(1)
