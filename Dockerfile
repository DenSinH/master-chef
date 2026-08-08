FROM python:3.14-slim-bookworm
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY ./pyproject.toml .
COPY ./uv.lock .
RUN uv sync --no-dev --frozen --no-progress --no-install-project

COPY . .

RUN uv sync --no-dev --frozen --no-progress
ENTRYPOINT ["uv", "run", "--no-sync", "master-chef"]
