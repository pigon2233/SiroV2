"""Standalone backend for hands-on computer-use verification (router only, no pet, no chat).

Env: SIRO_COMPUTER_TOKEN, SIRO_COMPUTER_ALLOWED_PROCESSES, SIRO_COMPUTER_CLOUD_SCREEN=1, PORT.
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from siro.services.computer_use.http import router_from_env


def main() -> None:
    router = router_from_env()
    if router is None:
        raise SystemExit("SIRO_COMPUTER_TOKEN is not set")
    app = FastAPI()
    app.include_router(router)
    uvicorn.run(
        app, host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), log_level="warning"
    )


if __name__ == "__main__":
    main()
