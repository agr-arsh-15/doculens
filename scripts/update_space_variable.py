"""Set one public variable on the DocuLens Space (the Space restarts to apply it).

  HF_TOKEN=... HF_SPACE=user/doculens-api .venv/bin/python scripts/update_space_variable.py CORS_ORIGINS "https://..."
"""
import os
import sys

from huggingface_hub import HfApi

if __name__ == "__main__":
    if len(sys.argv) != 3 or not os.environ.get("HF_TOKEN") or not os.environ.get("HF_SPACE"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    HfApi(token=os.environ["HF_TOKEN"]).add_space_variable(os.environ["HF_SPACE"], sys.argv[1], sys.argv[2])
    print(f"Updated {sys.argv[1]} on {os.environ['HF_SPACE']}.")
