FROM ghcr.io/astral-sh/uv:python3.11-trixie-slim

WORKDIR /usr/src/app

# Install dependencies only for better caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Install project
COPY src ./src
RUN uv sync --frozen

CMD [".venv/bin/python", "-m", "gge_utility_bot.main"]