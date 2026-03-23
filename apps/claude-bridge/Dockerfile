FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for claude CLI) and npm
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code 2>/dev/null || echo "Claude Code CLI install skipped (optional)"

COPY apps/claude-bridge/pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard]

COPY apps/claude-bridge/src ./src

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

ENV APP_ENV=development
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
