# O motor do Viking no Cloud Run (Sessão 10, D58). Construído no VPS (`scripts/nuvem.py deploy`),
# com a tag = o SHA do commit. Desde a Sessão 11d (D64) a mesma imagem roda também o serviço de
# finanças, com outro comando (`scripts/nuvem.py`, `--command`/`--args`).
# Copia só o que o motor precisa: nada de `.env`, `secrets/`, `data/`
# nem `.git` (o `.dockerignore` fecha, e `tests/test_dockerfile.py` confere as duas pontas).
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS construir

# `.pyc` pré-compilados de propósito: com 0 instâncias mínimas toda partida é fria.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.12.10

WORKDIR /app
# As dependências primeiro (camada reaproveitada enquanto o lock não muda), exatamente o uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra nuvem --no-install-project --no-editable
COPY src ./src
RUN uv sync --locked --extra nuvem --no-editable \
    && test -f /app/.venv/lib/python3.12/site-packages/lifeos/nuvem/motor.py \
    && test -f /app/.venv/lib/python3.12/site-packages/lifeos/nuvem/financas.py \
    && /app/.venv/bin/python -c "import zoneinfo; zoneinfo.ZoneInfo('America/Sao_Paulo')"

# A imagem final: a mesma base, só o ambiente pronto (sem o uv nem o pip de construir).
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=construir /app/.venv /app/.venv
ARG VIKING_COMMIT=""
ENV VIKING_COMMIT=${VIKING_COMMIT} VIKING_STORE=firestore
USER 65532:65532
EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "lifeos.nuvem.motor:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
