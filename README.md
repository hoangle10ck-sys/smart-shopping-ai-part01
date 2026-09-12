# Smart Shopping AI

Foundation for the project **Xây dựng hệ thống trợ lý mua hàng thông minh ứng dụng trí tuệ nhân tạo**.

## Stack

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: Python + FastAPI + Pydantic + SQLAlchemy
- MVP database: SQLite
- AI (later phases): Gemini API
- Web search (later phases): Tavily through a Search Provider abstraction

## Prerequisites

- Python 3.11+ recommended
- Node.js 20.9+
- VS Code

## Environment

Copy `.env.example` to `.env` in the project root.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## Run backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
fastapi dev app/main.py
```

Open:

- http://127.0.0.1:8000/api/health
- http://127.0.0.1:8000/api/system/status
- http://127.0.0.1:8000/docs

## Run tests

```powershell
cd backend
pytest
```

## Run frontend

Open a second VS Code terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.
