import os
import json
import logging

from pathlib import Path
from jsonschema import RefResolver, Draft7Validator, FormatChecker

logging.basicConfig(filename="json_validation.log", level=logging.INFO)
logger = logging.getLogger(__name__)


def get_schemas_store(path):
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    store = {}
    for schema_filename in files:
        if "json" in schema_filename:
            schema_path = os.path.join(path, schema_filename)
            with open(schema_path, "r") as schema_file:
                schema = json.load(schema_file)
                store[schema["$id"]] = schema
    return store


def validate_instance(path, filename, schema_filename, error_printing, instance):
    schema_path = os.path.split(schema_filename)[0]
    try:
        schema_file = open(schema_filename)
        schema = json.load(schema_file)
        schemastore = get_schemas_store(schema_path)
        resolver = RefResolver(
            base_uri=f"{Path.as_uri(Path(schema_path).absolute())}/",
            referrer=schema,
            store=schemastore,
        )
        validator = Draft7Validator(
            schema, resolver=resolver, format_checker=FormatChecker()
        )
        print("Validating " + filename + " against " + schema_filename)
        logger.info("Validating %s against %s ", filename, schema_filename)

        try:
            instance_file = open(os.path.join(path, filename))

            if instance is None:
                instance = json.load(instance_file)

            if error_printing:
                errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
                for error in errors:
                    print(error.message)
                    logger.error(error.message)

                if len(errors) == 0:
                    return True
                else:
                    return False

            elif error_printing == 0:
                errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
                for error in errors:
                    print(error.message)
                    logger.error(error.message)
                    for suberror in sorted(error.context, key=lambda e: e.schema_path):
                        print(list(suberror.schema_path), suberror.message)
                        logger.error(
                            "%s, %s", list(suberror.schema_path), suberror.message
                        )

                if len(errors) == 0:
                    logger.info("...done")
                    return True
                else:
                    return False
            else:
                try:
                    validator.validate(instance, schema)
                    logger.info("...done")
                    return True
                except Exception as e:
                    logger.error(e)
                    return False
        finally:
            instance_file.close()
    finally:
        schema_file.close()
