FROM python:3.12-slim
ARG UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_CACHE=1 \
    UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PORT=8080

WORKDIR /app
# Pin the same uv release used locally and in CI. Install from the configured
# index instead of copying the ghcr.io image (cloud builds often cannot pull it).
RUN pip install --index-url "${PIP_INDEX_URL}" "uv==0.13.7"

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
 && uv pip install --require-hashes -r /tmp/requirements.txt

COPY . .
RUN uv pip install --no-deps . \
 && useradd --system --uid 10001 app
USER app

EXPOSE 8080
CMD ["sh", "-c", "tennis-match-migrate --if-enabled && exec uvicorn tennis_match_api.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
