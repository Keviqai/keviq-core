"""Claude Code CLI Bridge — local-only model provider for Keviq Core.

⚠️  LOCAL-ONLY SERVICE — DO NOT DEPLOY IN SHARED/PRODUCTION ENVIRONMENTS.

This service bridges Keviq Core model-gateway requests to the locally-installed
Claude Code CLI.  It relies on the host user's existing Claude Code login
(via `claude login`) and never extracts or stores any authentication tokens.

Start: uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI

from src.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claude Code CLI Bridge",
    description="Local-only bridge: routes Keviq Core model calls through Claude Code CLI subscription",
    version="0.1.0",
)

app.include_router(router)


@app.on_event("startup")
def _startup_warnings():
    """Emit warnings at startup for safety."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        logger.warning(
            "⚠️  ANTHROPIC_API_KEY is set — this overrides Claude Code "
            "subscription auth and may cause unexpected API billing."
        )

    env = os.environ.get("APP_ENV", "development")
    if env not in ("development", "local", "test"):
        logger.error(
            "🚫 claude-bridge is LOCAL-ONLY and must not be deployed in "
            "shared/production environments (APP_ENV=%s). "
            "Shutting down.", env,
        )
        sys.exit(1)

    logger.info("claude-bridge started in %s mode (local-only)", env)
