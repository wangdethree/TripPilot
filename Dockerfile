FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system trippilot \
    && useradd --system --gid trippilot --home-dir /app trippilot
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -r /wheels

USER trippilot
EXPOSE 8000
CMD ["uvicorn", "trippilot.interfaces.http.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
