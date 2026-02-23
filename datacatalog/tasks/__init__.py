from celery import Celery, Task
from flask import Flask, current_app

from datacatalog.tasks import pdf  # noqa: F401


def dispatch_task(task, *args, **kwargs):
    if current_app.config.get("USE_CELERY", False) and "celery" in current_app.extensions:
        return task.delay(*args, **kwargs)

    return task.run(*args, **kwargs)


def celery_init_app(app: Flask) -> Celery:
    """Initialize Celery with Flask application context."""

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app

    return celery_app
