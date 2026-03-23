# ── Builder ──────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/policy-service/pyproject.toml /tmp/svc.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/svc.toml','rb'))['project']['dependencies']))" \
    | pip install --no-cache-dir -r /dev/stdin

COPY packages/logger/pyproject.toml /tmp/logger.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/logger.toml','rb'))['project']['dependencies']))" \
    | pip install --no-cache-dir -r /dev/stdin

# ── Runtime ──────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY apps/policy-service/alembic.ini ./alembic.ini
COPY apps/policy-service/alembic ./alembic
COPY apps/policy-service/src ./src
COPY packages/logger /repo/packages/logger
ENV PYTHONPATH="/repo/packages/logger:${PYTHONPATH}"

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
