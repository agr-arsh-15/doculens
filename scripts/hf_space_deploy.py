"""Create or update the DocuLens API Space on Hugging Face, set its secrets, and upload the backend.

Run from the repository root (the setup wizard does this for you):
  HF_TOKEN=... HF_SPACE=user/doculens-api SPACE_SECRETS_FILE=.env.deploy .venv/bin/python scripts/hf_space_deploy.py

Secrets and variables are read from SPACE_SECRETS_FILE (KEY=VALUE lines). Values are never printed.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ["SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL", "GROQ_API_KEY", "ENCRYPTION_KEY", "ADMIN_EMAILS"]
VARIABLES = ["APP_ENV", "AUTH_MODE", "SUPABASE_URL", "SUPABASE_STORAGE_BUCKET", "CORS_ORIGINS"]


def read_env(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    token, space = os.environ.get("HF_TOKEN"), os.environ.get("HF_SPACE")
    if not token or not space:
        print("HF_TOKEN and HF_SPACE are required.", file=sys.stderr)
        return 2
    values = read_env(ROOT / os.environ.get("SPACE_SECRETS_FILE", ".env.deploy"))
    missing = [k for k in SECRETS + VARIABLES if not values.get(k)]
    if missing:
        print(f"Missing values: {', '.join(missing)}", file=sys.stderr)
        return 2

    api = HfApi(token=token)
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    for key in SECRETS:
        api.add_space_secret(space, key, values[key])
    for key in VARIABLES:
        api.add_space_variable(space, key, values[key])
    print(f"Set {len(SECRETS)} secrets and {len(VARIABLES)} variables on {space}.")

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "space"
        shutil.copytree(ROOT / "backend", stage, ignore=shutil.ignore_patterns("data", "tests", "eval", "__pycache__",
                                                                                 ".pytest_cache", "*.db", ".env"))
        shutil.copy(ROOT / "deploy" / "hf-space" / "README.md", stage / "README.md")
        api.upload_folder(folder_path=str(stage), repo_id=space, repo_type="space",
                          commit_message="Deploy DocuLens API", delete_patterns=["app/**", "*.py", "*.txt", "*.ini"])
    print(f"Uploaded the backend. The Space is building: https://huggingface.co/spaces/{space}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
