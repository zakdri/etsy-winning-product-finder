# TrendScout local API

The FastAPI service keeps Etsy credentials outside the browser extension and returns normalized research results.

## Run from the repository root

```bat
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --reload
```

The service reads the existing root `.env` file. Do not commit that file.
