# PaperQuery Backend

FastAPI backend for PaperQuery. It provides user authentication, library/document APIs, PDF retrieval, translation, RAG chat, multi-model routing, and the background vectorization worker.

See the root `README.md` for full setup instructions.

## Local Services

Start API service:

```powershell
python main.py
```

Start document vectorization worker in another terminal:

```powershell
python vector.py
```

## Environment

Copy `.env.example` to `.env` and configure model API keys, Tencent translation credentials, JWT settings, SQLite path, and ChromaDB directories.

Do not commit `.env`, local PDFs, ChromaDB indexes, ONNX model cache, or SQLite database files.
