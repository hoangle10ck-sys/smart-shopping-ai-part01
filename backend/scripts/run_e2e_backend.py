"""Start an isolated Demo backend for Playwright; never open the developer DB."""

import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="smart-shopping-e2e-") as directory:
        database = Path(directory) / "e2e.sqlite3"
        os.environ.update(
            DATABASE_URL=f"sqlite:///{database.as_posix()}", DEMO_MODE="true",
            OPENAI_API_KEY="", GEMINI_API_KEY="", TAVILY_API_KEY="", APP_ENV="test",
        )
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

        # Fail closed if any application code accidentally attempts external I/O.
        original_connect = socket.socket.connect

        def local_connect(sock, address):
            if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
                raise RuntimeError("External network is disabled in browser E2E")
            return original_connect(sock, address)

        socket.socket.connect = local_connect
        from app.core.config import get_settings
        get_settings.cache_clear()
        from app.core.database import engine
        from app.main import app
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn

        assert Path(engine.url.database).resolve() == database.resolve()
        assert get_settings().demo_mode
        # Test-only origin, without changing application CORS or routes.
        app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:13000"],
                           allow_methods=["*"], allow_headers=["*"])
        try:
            uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
