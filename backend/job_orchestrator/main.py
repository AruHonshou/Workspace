from __future__ import annotations

import uvicorn

from .api import create_app
from .config import Settings

app = create_app()


def run() -> None:
    settings = Settings()
    uvicorn.run(
        "job_orchestrator.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
