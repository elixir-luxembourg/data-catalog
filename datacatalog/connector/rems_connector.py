#  coding=utf-8
#   DataCatalog
#   Copyright (C) 2020  University of Luxembourg
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from typing import List
import requests
from flask import url_for

from .entities_connector import ExportEntitiesConnector
from .rems_client import RemsClient
from .. import app
from ..exceptions import (
    CouldNotCloseApplicationException,
    CouldNotSubmitApplicationException,
)
from ..solr.solr_orm_entity import SolrEntity

logger = logging.getLogger(__name__)


class UserDoesntExistException(Exception):
    pass


class CatalogueItemDoesntExistException(Exception):
    pass


class RemsConnector(ExportEntitiesConnector):
    def __init__(
        self,
        api_username,
        api_key,
        host,
        workflow_id,
        organization_id=None,
        licenses=None,
        verify_ssl=True,
        admin_user=None,
    ):
        self.rems_client = RemsClient(
            base_url=host,
            api_key=api_key,
            api_username=api_username,
            admin_user=admin_user,
            verify_ssl=verify_ssl,
        )
        self.wfid = workflow_id
        self.organization_id = organization_id
        self.licenses = licenses

    def create_application(self, items):
        logger.info(
            "Creating Rems application for items %s", ",".join([str(i) for i in items])
        )
        response = self.rems_client.create_application(items)
        logger.info("Application with id %s created ", response.application_id)
        return response.application_id

    def save_application_draft(self, application_id, form_id, fields):
        logger.info("Saving application %s as draft", application_id)
        field_values = []
        for field_name, value in fields.items():
            field_values.append({"form": form_id, "field": field_name, "value": value})
        response = self.rems_client.save_draft(application_id, field_values)
        success = response.success
        if success:
            logger.info("Application saved")
        else:
            logger.info("Application was not saved")
        return success

    def export_entities(self, entities: List[SolrEntity]):
        logger.info("Exporting entities to REMS")
        resource_ids = self.load_resources()
        count = 0
        for entity in entities:
            # Skip exporting entity with e2e False or form_id None
            if not entity.e2e or getattr(entity, "form_id", None) is None:
                continue
            count += 1
            entity_name = type(entity).__name__.lower()
            logger.debug("exporting entity %s (%s)", entity.id, entity_name)
            res_id = entity.id
            # resource
            if res_id in resource_ids:
                res_id_int = resource_ids[res_id]
                logger.debug("resource already exists: %s", res_id_int)
            else:
                logger.debug("creating resource")
                result = self.rems_client.create_resource(
                    organization_id=self.organization_id,
                    resid=res_id,
                    license_ids=self.licenses,
                )
                res_id_int = result.id
                logger.debug("resource created: %s", res_id_int)
            # catalogue item
            localizations = {
                "en": {
                    "title": entity.title,
                    "infourl": app.config.get("BASE_URL", "")
                    + url_for(
                        "entity_details",
                        entity_name=entity_name,
                        entity_id=entity.id,
                    ),
                }
            }
            if res_id in resource_ids:
                logger.debug("checking if a catalogue entry already exists")
                items = self.rems_client.get_catalogue_items(resource=res_id)
                item_updated = False
                for item in items:
                    if (
                        item.form_id == getattr(entity, "form_id")
                        and item.wfid == self.wfid
                    ):
                        logger.debug("updating title and infourl")
                        self.rems_client.edit_catalogue_items(item.id, localizations)
                        item_updated = True
                        break
                if item_updated:
                    continue

            logger.debug("creating catalogue entry")
            self.rems_client.create_catalogue_items(
                res_id_int=res_id_int,
                form_id=getattr(entity, "form_id", None),
                wfid=self.wfid,
                localizations=localizations,
                organization_id=self.organization_id,
            )
        return count

    def load_resources(self):
        logger.debug("retrieving all resources from rems")

        all_resources = self.rems_client.get_resources()

        resources_ids = dict()
        for r in all_resources:
            if not r.archived and r.enabled:
                resources_ids[r.resid] = r.id
        logger.debug("%d resources found", len(resources_ids))
        return resources_ids

    def get_catalogue_item(self, entity):
        logger.debug(
            "getting catalogue item for %s %s", type(entity).__name__, entity.id
        )
        items = self.rems_client.get_catalogue_items(resource=entity.id)

        if len(items) == 0:
            message = f"no catalogue item found for resource {entity.id}"
            logger.warning(message)
            raise CatalogueItemDoesntExistException(message)
        else:
            if getattr(entity, "form_id", None) is not None:
                for item in items:
                    # return catalogue item that matches both dataset_id and form_id
                    if item.form_id == entity.form_id and item.wfid == self.wfid:
                        return item

            message = f"no catalogue item found for resource {entity.id}"
            logger.warning(message)
            raise CatalogueItemDoesntExistException(message)

    def get_resource(self, resource_id):
        logger.debug("getting resource for resource_id %s", resource_id)
        return self.rems_client.get_resource(resource_id)

    def get_form_for_catalogue_item(self, form_id):
        logger.debug("getting form for form id %s", form_id)
        return self.rems_client.get_form(form_id)

    def accept_license(self, application_id, license_ids):
        logger.info(
            "accepting licenses %s for application %s",
            ",".join([str(license) for license in license_ids]),
            application_id,
        )
        response = self.rems_client.accept_licenses(application_id, license_ids)
        if not response.success:
            raise CouldNotSubmitApplicationException("Failed to accept licenses")

    def submit_application(self, application_id):
        logger.info("submitting application %s", application_id)
        result = self.rems_client.submit_application(application_id)
        if not result.success:
            logger.error(f"Error submitting application: {result.errors}")
            raise CouldNotSubmitApplicationException(result.errors[0]["type"])

    def close_application(self, application_id):
        logger.info("closing application %s", application_id)
        try:
            self.rems_client.close_application(application_id)
        except requests.exceptions.HTTPError as e:
            raise CouldNotCloseApplicationException(e)

    def my_applications(self):
        logger.debug(
            "getting list of user's applications for user %s",
            self.rems_client.api_username,
        )
        try:
            return self.rems_client.get_my_applications()
        except requests.exceptions.HTTPError:
            return []

    def applications(self, query):
        logger.debug("getting list of applications for query %s", query)
        try:
            return self.rems_client.get_applications(query)
        except requests.exceptions.HTTPError:
            return []

    def create_user(self, user_id, name, email):
        logger.info("Creating REMS user %s (%s,%s)", user_id, name, email)
        return self.rems_client.create_user(user_id, name, email)

    def add_attachment(self, application_id, file_path):
        logger.info("adding attachment %s to application %s", file_path, application_id)
        return self.rems_client.add_attachment(application_id, file_path)

    def get_application(self, application_id):
        logger.debug("getting application %s", application_id)
        return self.rems_client.get_application(application_id)
