# Backend

Early-stage FastAPI application. Currently a Hello World shell — no routes, models,
or database integration yet.

## Stack
- FastAPI 0.135.3
- Uvicorn 0.44.0
- Pydantic 2.12.5
- Python-dotenv 1.2.2

## Entry Point
`main.py` — single root GET endpoint returning `{"message": "Hello World"}`.

## Start Dev Server
```bash
cd backend
uvicorn main:app --reload
```

## Do Not Touch
- `.venv/`
- `.env` (if present)
