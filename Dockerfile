# Builder stage: Install dependencies and build assets
FROM python:3.12.4

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DATACATALOG_ENV=docker \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/code/.venv/bin:$PATH"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install required packages
RUN apt-get update --no-install-recommends && \
    apt-get install -y \
        default-jre \
        nodejs \
        npm \
        build-essential \
        python3-dev \
        libldap2-dev \
        libsasl2-dev \
        ldap-utils \
        libreoffice-writer && \
    npm install -g lessc less && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Copy Python requirements
COPY pyproject.toml uv.lock /code/

# Install Python dependencies (without the project) for cache reuse
RUN uv sync --frozen --no-dev --no-install-project

# Copy static files and build assets
COPY ./datacatalog/static /code/datacatalog/static
RUN cd /code/datacatalog/static/vendor && \
    npm ci && \
    npm run build

# Copy source code
COPY . /code/

# Install the project itself
RUN uv sync --frozen --no-dev

RUN cp /code/datacatalog/settings.py.template /code/datacatalog/settings.py

# Compile Flask assets
RUN flask assets build

# Add a non-root user
RUN useradd -m datacat && chown -R datacat /code
USER datacat

EXPOSE 5023

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5023"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5023 || exit 1
