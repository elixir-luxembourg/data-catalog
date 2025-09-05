# Builder stage: Install dependencies and build assets
FROM python:3.12.4

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DATACATALOG_ENV=docker

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
        ldap-utils && \
    npm install -g lessc less && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Copy Python requirements
COPY pyproject.toml /code/

# Install Python dependencies
RUN pip install -e . --default-timeout=180 && \
    pip install gunicorn

# Copy static files and build assets
COPY ./datacatalog/static /code/datacatalog/static
RUN cd /code/datacatalog/static/vendor && \
    npm ci && \
    npm run build

# Copy source code
COPY . /code/

RUN cp /code/datacatalog/settings.py.template /code/datacatalog/settings.py

# Compile Flask assets
RUN /usr/local/bin/flask assets build

WORKDIR /code

# Add a non-root user
RUN useradd -m datacat && chown -R datacat /code
USER datacat

EXPOSE 5023

ENTRYPOINT ["python"]
CMD ["/usr/local/bin/flask", "run", "--host", "0.0.0.0", "--port", "5023"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5023 || exit 1
