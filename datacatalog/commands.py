#!/usr/bin/env python

#  DataCatalog
#  Copyright (C) 2020  University of Luxembourg
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
 commands.py
 -------------------

Entry points for CLI operations:
   - indexer init: initialize the solr index by creating the fields
   - indexer update: update the solr index by updating the fields
   - indexer clear: delete entities from index
   - indexer commit: triggers a solr commit
   - import entities: import entities into solr
   - export entities: export entities to a target connector

"""

import click
from flask import Flask
from flask.cli import AppGroup

import requests


def register_cli(app: Flask):
    def exit_if_schema_incomplete(solr_orm, entity_name):
        """
        Abort the command if the solr schema misses fields the entity declares.
        The library only reports which fields are missing; naming the command
        that recreates the schema is up to us.
        @param solr_orm: the SolrORM instance
        @param entity_name: type of the entities being processed, e.g. dataset
        """
        try:
            missing = solr_orm.missing_fields(entity_name)
        except KeyError:
            app.logger.error("unknown entity name %s", entity_name)
            exit(1)
        if missing:
            app.logger.error(
                "The solr schema is incomplete for entity '%s': %d field(s) "
                "missing (%s). Run `flask indexer init` first.",
                entity_name,
                len(missing),
                ", ".join(missing),
            )
            exit(1)

    def exit_if_field_types_mismatch(solr_orm, entity_name):
        """
        Abort the command if a field type differs between the solr schema and
        the entity definition. As above, the library reports the mismatches and
        we name the command that fixes them.
        @param solr_orm: the SolrORM instance
        @param entity_name: type of the entities being processed, e.g. dataset
        """
        try:
            mismatches = solr_orm.mismatched_fields(entity_name)
        except KeyError:
            app.logger.error("unknown entity name %s", entity_name)
            exit(1)
        if mismatches:
            app.logger.error(
                "Solr field type mismatch for entity '%s': %s. "
                "Run `flask indexer init` to rebuild the schema.",
                entity_name,
                "; ".join(
                    f"{name} is {actual} in the schema but declared as {expected}"
                    for name, expected, actual in mismatches
                ),
            )
            exit(1)

    def register_indexer_commands():
        indexer_cli = AppGroup("indexer")

        @indexer_cli.command("init")
        def init_index():
            """
            Initialize the solr schema by creating the fields defined by the different SolrEntity subclasses
            Safe to re-run: fields that already exist are left as they are.

            Use 'indexer update' instead to change the definition of a field
            that already exists, which does require a reindex.
            """
            solr_orm = app.config["_solr_orm"]
            try:
                # create_fields only adds what the schema lacks, so an existing
                # collection no longer has to be emptied of its fields first --
                # which used to discard everything indexed in it
                solr_orm.create_fields()
                solr_orm.solr_config_update()
            except requests.exceptions.HTTPError as e:
                app.logger.warning(e)
                app.logger.error("The solr schema was not fully initialized.")
                exit(1)
            entity_names = ", ".join(sorted(app.config["entities"]))
            incomplete = [
                entity_name
                for entity_name in sorted(app.config["entities"])
                if solr_orm.missing_fields(entity_name)
            ]
            if incomplete:
                app.logger.error(
                    "The solr schema is still incomplete for: %s. "
                    "Check the warnings above.",
                    ", ".join(incomplete),
                )
                exit(1)
            app.logger.info("Solr schema initialized for %s.", entity_names)

        @indexer_cli.command("update")
        def update_index():
            """
            Update the solr schema by updated the fields defined by the different SolrEntity subclasses
            The fields should already exist before executing this operation.
            """
            solr_orm = app.config["_solr_orm"]
            solr_orm.update_fields()

        @indexer_cli.command("clear")
        @click.argument("entity_type")
        def clear_index(entity_type):
            """
            Delete all instance of the specified entity type.
            Doesn't trigger a commit but will clear the cache.
            @param entity_type: name of the entity type, e.g. dataset
            """
            solr_orm = app.config["_solr_orm"]
            if entity_type == "all":
                query = "*:*"
            else:
                query = f"type:{entity_type}"
            solr_orm.delete(query=query)
            app.cache.clear()

        @indexer_cli.command("commit")
        def commit_changes():
            """
            Triggers a solr commit.
            """
            solr_orm = app.config["_solr_orm"]
            solr_orm.commit()

        @indexer_cli.command("extend")
        @click.argument("entity_name")
        def extend_entity_index(entity_name):
            from datacatalog.connector.extend_entity_index import EntitiesIndexExtender

            if entity_name not in app.config["entities"]:
                app.logger.error("unknown entity name")
                exit(1)
            if entity_name.lower() == "project":
                EntitiesIndexExtender.extend_project_index()
            if entity_name.lower() == "study":
                EntitiesIndexExtender.extend_study_index()
            if entity_name.lower() == "dataset":
                EntitiesIndexExtender.extend_dataset_index()

        @indexer_cli.command("drop_connector_entities")
        @click.argument("connector_name")
        @click.argument("entity_name")
        def drop_connector_entities(connector_name, entity_name):
            """
            Unpublish entities of type entity_name using the connector specified by connector_name
            Trigger a commit and clear the cache.
            Checks for type mismatch for each field
            @param connector_name: Short name of the connector to use, e.g. Json. See method get_importer_connector
            @type entity_name: type of the entities to delete
            """
            solr_orm = app.config["_solr_orm"]
            exit_if_schema_incomplete(solr_orm, entity_name)
            if entity_name not in app.config["entities"]:
                app.logger.error("unknown entity name")
                exit(1)
            entity_class = app.config["entities"][entity_name]
            connector = get_importer_connector(connector_name, entity_class)
            exit_if_field_types_mismatch(solr_orm, entity_name)
            if not connector:
                app.logger.error("no known connector found")
                exit(1)

            solr_orm.delete(
                query=f"{entity_name}_connector_name:{connector.__class__.__name__}"
            )
            solr_orm.commit()
            app.logger.info(
                f"All {entity_name}(s) of {connector.__class__.__name__} were deleted"
            )
            app.cache.clear()

        app.cli.add_command(indexer_cli)

    def register_importer_commands():
        importer_cli = AppGroup(
            "import", help="Import entities from a source connector into the index."
        )

        @importer_cli.command(
            "entities",
            short_help="Import entities of one type from a connector.",
        )
        @click.argument("connector_name", metavar="CONNECTOR")
        @click.argument("entity_name", metavar="ENTITY")
        @click.option(
            "--sitemap/--no-sitemap",
            default=False,
            help="Regenerate the sitemaps after the import (default: --no-sitemap).",
        )
        def import_entities(connector_name, entity_name, sitemap=False):
            """Import entities of type ENTITY using the CONNECTOR source.

            \b
            CONNECTOR  source to read from, one of:
                       Dats, Json, csv, Geo, Daisy, Limesurvey,
                       plus any name declared in the IMPORTERS_EXTRA setting.
            ENTITY     entity type to import: study, project or dataset
                       (the keys of the ENTITIES setting).

            The connector must be listed in the entity's COMPATIBLE_CONNECTORS,
            and the Solr schema must already exist -- run `flask indexer init`
            first. The import clears the application cache but does not commit
            to Solr; run `flask indexer commit` when done.

            \b
            Examples:
              flask import entities Dats study
              flask import entities Dats dataset --sitemap
            """
            solr_orm = app.config["_solr_orm"]
            exit_if_schema_incomplete(solr_orm, entity_name)
            if entity_name not in app.config["entities"]:
                app.logger.error("unknown entity name")
                exit(1)
            entity_class = app.config["entities"][entity_name]
            connector = get_importer_connector(connector_name, entity_class)
            exit_if_field_types_mismatch(solr_orm, entity_name)
            if not connector:
                app.logger.error("no known connector found")
                exit(1)
            from datacatalog.importer.entities_importer import EntitiesImporter

            importer = EntitiesImporter([connector])
            importer.import_all()
            if sitemap:
                generate_sitemaps()
            app.cache.clear()

        app.cli.add_command(importer_cli)

    def register_exporter_commands():
        exporter_cli = AppGroup("export")

        @exporter_cli.command("entities")
        @click.argument("connector_name")
        @click.argument("entity_name")
        def export_entities(connector_name, entity_name):
            """
            Import entities of type entity_name using the connector specified by connector_name
            @param connector_name: Short name of the connector to use, e.g. Rems.
            @type entity_name: type of the entities to import
            """
            if entity_name not in app.config["entities"]:
                app.logger.error("unknown entity name")
                exit(1)
            entity_class = app.config["entities"][entity_name]
            from datacatalog.exporter.entities_exporter import EntitiesExporter
            from datacatalog.connector.rems_connector import RemsConnector

            connector = RemsConnector(
                api_username=app.config.get("REMS_API_USER"),
                api_key=app.config.get("REMS_API_KEY"),
                host=app.config.get("REMS_URL"),
                workflow_id=app.config.get("REMS_WORKFLOW_ID"),
                organization_id=app.config.get("REMS_ORGANIZATION_ID"),
                licenses=app.config.get("REMS_LICENSES"),
                verify_ssl=app.config.get("REMS_VERIFY_SSL", True),
            )
            if not connector:
                app.logger.error("no known connector found")
                exit(1)
            entities = entity_class.query.all()
            exporter = EntitiesExporter([connector])
            exporter.export_all(entities)

        app.cli.add_command(exporter_cli)

    @app.cli.command("clear_cache")
    def clear_cache():
        """
        Clear the cache
        """
        app.cache.clear()

    @app.cli.command("generate_sitemaps")
    def generate_sitemaps():
        """
        Generates a sitemap with each route for each entity.
        """
        from datacatalog.controllers.sitemap_generator import generate_sitemap

        try:
            if generate_sitemap():
                app.logger.info("Sitemap was Generated")
        except FileNotFoundError as e:
            app.logger.error(e)

    register_indexer_commands()
    register_importer_commands()
    register_exporter_commands()

    def get_importer_connector(connector_name, entity_class):
        """
        Returns an instance of the connector corresponding to connector_name
        Will check if the entity_class is compatible with the connector asked.
        @param connector_name: the name of the connector asked
        @param entity_class: The class of the entity we want to index
        @return:  instance or None
        @rtype: DatasetConnector
        """
        connector = None
        importer_extra = app.config.get("IMPORTERS_EXTRA", {}).get(connector_name)
        if connector_name not in entity_class.COMPATIBLE_CONNECTORS:
            app.logger.error("connector and entity name not compatible")
            exit(1)
        elif connector_name == "Geo":
            from datacatalog.connector.geostudies_connector import GEOStudiesConnector

            connector = GEOStudiesConnector(
                app.config["GEO_FILE_PATH"][entity_class.__name__.lower()], entity_class
            )
        elif connector_name == "Json":
            from datacatalog.connector.json_connector import JSONConnector

            connector = JSONConnector(
                app.config["JSON_FILE_PATH"][entity_class.__name__.lower()],
                entity_class,
            )
        elif connector_name == "csv":
            from datacatalog.connector.csv_connector import CSVConnector

            connector = CSVConnector(
                app.config["CSV_FILE_PATH"][entity_class.__name__.lower()], entity_class
            )
        elif connector_name == "Dats":
            from datacatalog.connector.dats_connector import DATSConnector

            connector = DATSConnector(
                app.config["JSON_FILE_PATH"][entity_class.__name__.lower()],
                entity_class,
            )
        elif connector_name == "Daisy":
            from datacatalog.connector.daisy_connector import DaisyConnector

            connector = DaisyConnector(
                app.config["DAISY_API_URLS"][entity_class.__name__.lower()],
                entity_class,
                verify_ssl=app.config.get("DAISY_VERIFY_SSL", True),
            )
        elif connector_name == "Limesurvey":
            from datacatalog.connector.limesurvey_connector import LimesurveyConnector

            connector = LimesurveyConnector(
                app.config["LIMESURVEY_URL"],
                app.config["LIMESURVEY_USERNAME"],
                app.config["LIMESURVEY_PASSWORD"],
                app.config["LIMESURVEY_SURVEY_ID"],
            )
        elif importer_extra:
            # allow specifying custom importers in settings.py IMPORTERS_EXTRA parameter
            split = importer_extra.split(".")
            importer_class_string_module = ".".join(split[:-1])
            importer_class_string_class = "".join(split[-1:])
            importer_module = __import__(
                importer_class_string_module, fromlist=[importer_class_string_class]
            )
            importer_class = getattr(importer_module, importer_class_string_class)
            connector = importer_class.get_default_instance(entity_class)
        return connector
