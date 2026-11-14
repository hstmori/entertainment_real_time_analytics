FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONTRACTS_DIR=/app/contracts/jsonschema

WORKDIR /app

COPY pyproject.toml TECHNICAL_README.md ./
COPY src ./src
COPY contracts ./contracts
COPY sql ./sql

RUN python -m pip install --no-cache-dir . && \
    useradd --uid 10001 --create-home appuser

FROM base AS runtime

USER 10001
ENTRYPOINT ["python", "-m", "entertainment_pipeline.producer"]
CMD ["--count", "100", "--rate", "20", "--seed", "42"]

FROM base AS processor

USER 10001
ENTRYPOINT ["python", "-m", "entertainment_pipeline.stream_processor"]
CMD ["--batch-size", "100", "--flush-interval", "10"]

FROM base AS gold

USER 10001
ENTRYPOINT ["python", "-m", "entertainment_pipeline.gold_builder"]
CMD ["--sql-dir", "/app/sql/gold"]

FROM base AS test

USER root
COPY tests ./tests
COPY infra ./infra
COPY scripts/oci ./scripts/oci
COPY scripts/*.py ./scripts/
RUN python -m pip install --no-cache-dir ".[dev]"

USER 10001
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-q"]

