import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    reload = os.environ.get("RELOAD", "1") == "1"
    print(f"Starting DocuLens API on http://{host}:{port} (docs at /docs)")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload, app_dir=str(backend_dir))
