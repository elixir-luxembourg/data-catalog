# Data Catalogue

A tool for advertising bio-medical **projects** and their associated **datasets**

The catalogue enhances visibility and accessibility of biomedical datasets, fostering collaboration and accelerating research. It supports data sharing, compliance, and reproducibility across the research ecosystem.

Developed through lean, user-centered design, the catalogue integrates community-accepted metadata models and supports diverse data types. It continues to grow through contributions from ELIXIR-LU and partner projects.</p>

## Instances:

This software is behind the following instances:

* [ELIXIR Luxembourg Data Catalogue](https://datacatalog.elixir-luxembourg.org)
* [Biomap Cohort Catalog](https://biomap-cohort-catalog.uni.lu)

## Acknowledgement
Initially launched as the [Translational Data Catalogue](https://github.com/FAIRplus/imi-data-catalogue) under IMI and H2020 initiatives jointly developed through ELIXIR Luxembourg, IMI-FAIRplus and IMI-eTRIKS collaborations. Over time, its development and support have evolved into a broader service now provided by ELIXIR Luxembourg.

## License
The code is available under **AGPL-3.0 license**. 

## Table of content

* [Local installation](#local-installation)
    * [Requirements](#requirements)
    * [Procedure](#procedure)
    * [Testing](#testing)
* [Background Tasks (Celery)](#background-tasks-celery)
* [Docker-compose build](#docker-compose-build)
    * [Requirements](#requirements-for-docker-compose-build)
    * [Building](#building)
    * [Maintenance](#maintenance-of-docker-compose)
    * [Modifying the datasets](#modifying-the-datasets)
* [Single Docker deployment](#single-docker-deployment)
* [Development](#development)

## Local installation

Local installation of development environment and procedure for docker version are described below.

### Requirements

Python ≥ 3.10
[uv](https://docs.astral.sh/uv/) ≥ 0.8
Solr ≥ 8.2  
npm ≥ 7.5.6

#### For Ubuntu

```
sudo apt-get install libsasl2-dev libldap2-dev libssl-dev
```

##### Background Tasks Rocky Linux 8

```bash
sudo dnf install pango cairo gdk-pixbuf2 libffi-devel
sudo dnf install libreoffice-writer
sudo dnf install redis
sudo systemctl enable --now redis
```

> **Note:** Rocky 8 ships Pango 1.42.4, while WeasyPrint >= 53 calls Pango >= 1.44
> APIs unconditionally (e.g. `pango_context_set_round_glyph_positions`), which
> fails at PDF render time with an `undefined symbol` error. WeasyPrint is
> therefore pinned to `< 53` in `pyproject.toml`. Do not bump it unless the host
> provides Pango >= 1.44 (not available in stock Rocky 8 repos).

### Procedure

1. Install python requirements with:

    ```
    uv sync
    ```

   Install the `lftclient` (required for the LFT downloads handler):

    ```
    uv pip install -e lftpythonclient --upgrade
    ```

1. The less compiler needs to be installed to generate the css files.

    ```
    sudo npm install less -g
    ```

1. Create the setting.py file by copying the template:
    ```
    cp datacatalog/settings.py.template datacatalog/settings.py
    ```
1. Modify the setting file (in datacatalog folder) according to your local environment. The SECRET_KEY parameter needs
   to be filled with a random string. For maximum security, generate it using python:
   ```python
   import os
   os.urandom(24)
    ```
1. Install the npm dependencies with:

    ```bash
    cd datacatalog/static/vendor
    npm ci
    npm run build
    ```
1. Create a solr core

    ```bash
    $SOLR_INSTALLATION_FOLDER/bin/solr start
    $SOLR_INSTALLATION_FOLDER/bin/solr create_core -c datacatalog
    ```

1. Back to the application folder, build the assets:

    ```
    uv run flask assets build
    ```

1. Initialize the solr schema:

    ```
    uv run flask indexer init
    ```
1. Index the provided studies, projects and datasets.
For local development, change `JSON_FILE_PATH` from `'data/imi_projects'`to `'tests/data/imi_projects_test'` or use data from [dats-elixir-files](https://gitlab.lcsb.uni.lu/core-services/datacatalog/dats-elixir-files).

     ```
     uv run flask import entities Dats study
     uv run flask import entities Dats project
     uv run flask import entities Dats dataset
     ```
1. [Optional] Automatically generate sitemap while indexing the datasets:

   ```
   uv run flask import entities Dats study --sitemap
   uv run flask import entities Dats project --sitemap
   uv run flask import entities Dats dataset --sitemap
   ```
1. Generate Sitemap:

     ```
     uv run flask generate_sitemaps
     ```
1. [Optional] Extend Index for studies, projects and datasets:

      ```
      uv run flask indexer extend project
      uv run flask indexer extend study
      uv run flask indexer extend dataset
      ```
1. [Optional] Drop connector entities - removes connector entities from solr:

      ```
      uv run flask indexer drop_connector_entities Daisy dataset
      ```

1. [Optional] Customize the [About](./datacatalog/templates/about.html) and [Help](./datacatalog/templates/help.html) pages to reflect your services.

1. Run the development server:

     ```
     uv run flask run
     ```

The application should now be available under http://localhost:5000

### Testing

To run the unit tests:

```
uv run pytest
```

Note that a different core is used for tests and will have to be created. By default, it should be called
datacatalog_test.

## Background Tasks (Celery)

The application uses Celery with Redis for background task processing.

### Requirements

Redis must be running:

```bash
sudo dnf install pango cairo gdk-pixbuf2 libffi-devel
sudo dnf install libreoffice-writer
sudo dnf install redis
sudo systemctl enable --now redis

# Linux
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis
```

### Running the Worker

Start the Celery worker in a separate terminal:

```bash
# Development
USE_CELERY=true uv run celery -A celery_worker:celery_app worker --loglevel=info

# With periodic task scheduler (beat)
USE_CELERY=true uv run celery -A celery_worker:celery_app worker --beat --loglevel=info

# Production (with concurrency)
USE_CELERY=true uv run celery -A celery_worker:celery_app worker --loglevel=warning --concurrency=4
```

For local (non-Docker) async execution, start the web app with the same flag:

```bash
USE_CELERY=true uv run flask run
```

### Configuration

Celery is configured via the `CELERY` dict in `settings.py`. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `broker_url` | `redis://localhost:6379/0` | Message broker URL |
| `result_backend` | `redis://localhost:6379/0` | Task result storage |
| `task_time_limit` | `300` | Hard time limit (seconds) |
| `task_soft_time_limit` | `240` | Soft time limit (seconds) |

Environment variables `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` can override defaults.
Set `USE_CELERY=true` to enable asynchronous task dispatch; when false, tasks run synchronously.

## Docker-compose build

Thanks to docker-compose, it is possible to easily manage all the components (solr and web server) required to run the
application.

### Requirements for docker-compose build

Docker and git must be installed.

### Building

`(local)` and `(web container)` indicate context of execution.

1. First, generate the certificates that will be used to enable HTTPS in reverse proxy. To do so, change directory
   to `docker/nginx/` and execute `generate_keys.sh` (relies on OpenSSL). If you don't plan to use HTTPS or just want to
   see demo running, you can skip this (warning - it would cause the HTTPS connection to be unsafe!).

1. Then, copy `datacatalog/settings.py.template` to `datacatalog/settings.py`. Edit the `settings.py` file to add a
   random string of characters in `SECRET_KEY`. For maximum security use:

   ```
   import os
   os.urandom(24)
   ```
   in python to generate this key.

   Then build and start the docker containers by running:

   ```
   (local) $ docker-compose up --build
   ```

   That will create a container with datacatalog web application, and a container for solr (the data will be persisted
   between runs).

1. Then, to create solr cores, execute in another console:

   ```
   (local) $ docker-compose exec solr solr create_core -c datacatalog
   (local) $ docker-compose exec solr solr create_core -c datacatalog_test

   ```

1. Then, to fill solr data:

   ```
   (local) $ docker-compose exec web /bin/bash
   (web container) $ flask indexer init
   (web container) $ flask import entities Dats study
   (web container) $ flask import entities Dats project
   (web container) $ flask import entities Dats dataset

   (PRESS CTRL+D or type: "exit" to exit)
   ```
1. The web application should now be available with loaded data via http://localhost and https://localhost with ssl
   connection (beware that most browsers display a warning or block self-signed certificates)

   Note: Redis and Celery worker are optional and enabled with the `celery` profile:
   ```
   (local) $ USE_CELERY=true docker-compose --profile celery up --build
   ```
   Check worker logs with:
   ```
   (local) $ docker-compose logs -f celery
   ```

### Maintenance of docker-compose

Docker container keeps the application in the state that it has been when it was built. Therefore, if you change any
files in the project, in order to see changes in application the container has to be rebuilt:

```
docker-compose up --build
```

If you wanted to delete solr data, you need to run (that will remove any persisted data - you must
redo `solr create_core`):

```
docker-compose down --volumes
```

### Modifying the datasets

The datasets, projects and studies are all defined in the files located in the folder `data/imi_projects`. Those files
can me modified to add, delete and modify those entities. After saving the files, rebuild and restart docker-compose
with:

```
CTLR+D
```

to stop all the containers

```
docker-compose up --build
```

to rebuild and restart the containers

```
(local) $ docker-compose exec web /bin/bash
(web container) $ flask import entities Dats study 
(web container) $ flask import entities Dats project
(web container) $ flask import entities Dats dataset
 

(PRESS CTRL+D or type: "exit" to exit)
```

To reindex the entities

## Single Docker deployment

In some cases, you might not want Solr and Nginx to run (for example if there are multiple instances of Data Catalog
runnning). Then, simply use:

```
(local) $ docker build . -t "data-catalog"
(local) $ docker run --name data-catalog --entrypoint "gunicorn" -p 5000:5000 -t data-catalog -t 600 -w 2 datacatalog:app --bind 0.0.0.0:5000
```

## Development

Install all dependencies (runtime + dev + testing) with:

```
uv sync --all-groups
```

Linting and formatting use [ruff](https://docs.astral.sh/ruff/); type checking uses [ty](https://docs.astral.sh/ty/).

```
uv run ruff check .
uv run ruff format .
uv run ty check
```

Install the pre-commit hooks (ruff, ty, eslint):

```
uvx pre-commit install
```
