# coding=utf-8

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

import shutil
import tempfile
from os import path
from unittest.mock import patch
from io import BytesIO

import requests_mock
from werkzeug.datastructures import FileStorage

from datacatalog import app
from datacatalog.acces_handler.rems_handler import FieldBuilder
from datacatalog.connector.rems_connector import (
    RemsConnector,
    CatalogueItemDoesntExistException,
)
from datacatalog.models.dataset import Dataset
from tests.base_test import BaseTest

__author__ = "Nirmeen Sallam"


REMS_URL = app.config.get("REMS_URL", "http://rems-mock-host")
REMS_API_USER = app.config.get("REMS_API_USER", "test-api-user")
REMS_API_KEY = app.config.get("REMS_API_KEY", "test-api-key")
REMS_WORKFLOW_ID = app.config.get("REMS_WORKFLOW_ID", 5)
REMS_ORGANIZATION_ID = app.config.get(
    "REMS_ORGANIZATION_ID", "89fca267-693e-41e1-830b-b4e6326c1dd0"
)
REMS_LICENSES = app.config.get("REMS_LICENSES", [1, 2])
REMS_VERIFY_SSL = False


@requests_mock.Mocker()
class TestRemsConnector(BaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.solr_orm = app.config["_solr_orm"]
        cls.solr_orm.delete_fields()
        cls.solr_orm.create_fields()

    def setUp(self):
        self.assertTrue(self.app.testing)
        title = "Great dataset!"
        self.dataset = Dataset(title)
        self.dataset.e2e = True
        self.dataset.form_id = 3
        self.dataset_id = self.dataset.id
        self.dataset.save()
        self.solr_orm.commit()

        self.rems_connector = RemsConnector(
            REMS_API_USER,
            REMS_API_KEY,
            REMS_URL,
            REMS_WORKFLOW_ID,
            REMS_ORGANIZATION_ID,
            REMS_LICENSES,
            REMS_VERIFY_SSL,
        )

    def test_create_application(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock get_catalogue_item calls with all required fields
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        response_id = self.rems_connector.create_application([catalogue_item.id])
        self.assertIsNotNone(response_id)

    def test_save_application_draft(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock get_form calls
        m.get(
            f"{REMS_URL}/api/forms/3",
            json={
                "form/id": 3,
                "archived": False,
                "enabled": True,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "form/fields": [
                    {
                        "field/id": "field1",
                        "field/type": "text",
                        "field/title": {"en": "Test Field"},
                        "field/optional": False,
                    }
                ],
            },
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )
        # Mock save_application_draft call
        m.post(
            f"{REMS_URL}/api/applications/save-draft",
            json={"success": True},
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        rems_form = self.rems_connector.get_form_for_catalogue_item(
            catalogue_item.form_id
        )
        field_values = {}
        # create application
        application_id = self.rems_connector.create_application([catalogue_item.id])
        for field in rems_form.fields:
            rems_field_id = field.fieldid
            wtf_field = FieldBuilder.build_field_builder(field)
            flask_form_value = "test"
            field_values[rems_field_id] = wtf_field.transform_value(
                flask_form_value, self.rems_connector, application_id
            )
        # save draftFormTemplate
        response = self.rems_connector.save_application_draft(
            application_id, rems_form.id, field_values
        )
        self.assertTrue(response)

    def test_export_entities_already_exported(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        self.rems_connector.export_entities([self.dataset])
        catalogue_item_2 = self.rems_connector.get_catalogue_item(self.dataset)
        self.assertEqual(catalogue_item.resid, catalogue_item_2.resid)

    def test_load_resources(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock load_resources call
        m.get(
            f"{REMS_URL}/api/resources",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "enabled": True,
                    "archived": False,
                    "organization": {
                        "organization/id": "test-org",
                        "organization/short-name": {"en": "Test Org"},
                        "organization/name": {"en": "Test Organization"},
                    },
                    "licenses": [],
                    "resource/duo": {},
                }
            ],
        )

        self.rems_connector.export_entities([self.dataset])
        resources_ids = self.rems_connector.load_resources()
        self.assertIsNotNone(resources_ids)

    def test_get_catalogue_item(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        self.assertEqual(catalogue_item.resid, self.dataset_id)

    def test_get_catalogue_item_matching_formid(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        self.assertEqual(catalogue_item.resid, self.dataset_id)
        self.assertEqual(catalogue_item.form_id, self.dataset.form_id)

    def test_get_catalogue_item_not_found(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )

        self.rems_connector.export_entities([self.dataset])
        self.dataset.form_id = None
        self.assertRaises(
            CatalogueItemDoesntExistException,
            self.rems_connector.get_catalogue_item,
            self.dataset,
        )

    def test_get_resource(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock get_resource call
        m.get(
            f"{REMS_URL}/api/resources/1",
            json={
                "id": 1,
                "resid": self.dataset_id,
                "enabled": True,
                "archived": False,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "licenses": [],
                "resource/duo": {},
            },
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        resource = self.rems_connector.get_resource(catalogue_item.resource_id)
        self.assertEqual(resource.resid, catalogue_item.resid)

    def test_get_form_for_catalogue_item(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock get_form call
        m.get(
            f"{REMS_URL}/api/forms/3",
            json={
                "form/id": 3,
                "archived": False,
                "enabled": True,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "form/fields": [
                    {
                        "field/id": "field1",
                        "field/type": "text",
                        "field/title": {"en": "Test Field"},
                        "field/optional": False,
                    }
                ],
            },
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        form = self.rems_connector.get_form_for_catalogue_item(catalogue_item.form_id)
        self.assertIsNotNone(form)

    def test_accept_license(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )
        # Mock get_resource call
        m.get(
            f"{REMS_URL}/api/resources/1",
            json={
                "id": 1,
                "resid": self.dataset_id,
                "enabled": True,
                "archived": False,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "licenses": [
                    {
                        "id": 1,
                        "licensetype": "license",
                        "organization": {
                            "organization/id": "test-org",
                            "organization/short-name": {"en": "Test Org"},
                            "organization/name": {"en": "Test Organization"},
                        },
                        "enabled": True,
                        "archived": False,
                        "localizations": {"en": {"title": "Test License"}},
                    }
                ],
                "resource/duo": {},
            },
        )
        # Mock get_application calls - first without accepted licenses, then with
        m.get(
            f"{REMS_URL}/api/applications/123",
            [
                {
                    "json": {
                        "application/id": 123,
                        "application/state": "draft",
                        "application/accepted-licenses": {},
                        "application/applicant": {
                            "userid": "test-user",
                            "name": "Test User",
                            "email": "test@example.com",
                        },
                        "application/resources": [],
                        "application/forms": [],
                        "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                        "application/created": "2023-01-01T00:00:00Z",
                        "application/modified": "2023-01-01T00:00:00Z",
                        "application/last-activity": "2023-01-01T00:00:00Z",
                    }
                },
                {
                    "json": {
                        "application/id": 123,
                        "application/state": "draft",
                        "application/accepted-licenses": {"test-user": [1]},
                        "application/applicant": {
                            "userid": "test-user",
                            "name": "Test User",
                            "email": "test@example.com",
                        },
                        "application/resources": [],
                        "application/forms": [],
                        "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                        "application/created": "2023-01-01T00:00:00Z",
                        "application/modified": "2023-01-01T00:00:00Z",
                        "application/last-activity": "2023-01-01T00:00:00Z",
                    }
                },
            ],
        )
        # Mock accept_license call
        m.post(
            f"{REMS_URL}/api/applications/accept-licenses",
            json={"success": True},
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        application_id = self.rems_connector.create_application([catalogue_item.id])
        resource_id = catalogue_item.resource_id
        resource = self.rems_connector.get_resource(resource_id)
        licenses = resource.licenses
        license_ids = []
        for license in licenses:
            license_id = license.id
            license_ids.append(license_id)

        application = self.rems_connector.get_application(application_id)
        self.assertFalse(application.accepted_licenses)

        self.rems_connector.accept_license(application_id, license_ids)

        application = self.rems_connector.get_application(application_id)
        self.assertTrue(application.accepted_licenses)

    def test_submit_application(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock get_form call
        m.get(
            f"{REMS_URL}/api/forms/3",
            json={
                "form/id": 3,
                "archived": False,
                "enabled": True,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "form/fields": [
                    {
                        "field/id": "fld1",
                        "field/type": "text",
                        "field/title": {"en": "Test Field"},
                        "field/optional": False,
                    }
                ],
            },
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )
        # Mock save_application_draft call
        m.post(
            f"{REMS_URL}/api/applications/save-draft",
            json={"success": True},
        )
        # Mock get_resource call
        m.get(
            f"{REMS_URL}/api/resources/1",
            json={
                "id": 1,
                "resid": self.dataset_id,
                "enabled": True,
                "archived": False,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "licenses": [
                    {
                        "id": 1,
                        "licensetype": "license",
                        "organization": {
                            "organization/id": "test-org",
                            "organization/short-name": {"en": "Test Org"},
                            "organization/name": {"en": "Test Organization"},
                        },
                        "enabled": True,
                        "archived": False,
                        "localizations": {"en": {"title": "Test License"}},
                    }
                ],
                "resource/duo": {},
            },
        )
        # Mock get_application calls - first without first_submitted, then with
        m.get(
            f"{REMS_URL}/api/applications/123",
            [
                {
                    "json": {
                        "application/id": 123,
                        "application/state": "draft",
                        "application/accepted-licenses": {},
                        "application/applicant": {
                            "userid": "test-user",
                            "name": "Test User",
                            "email": "test@example.com",
                        },
                        "application/resources": [],
                        "application/forms": [],
                        "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                        "application/created": "2023-01-01T00:00:00Z",
                        "application/modified": "2023-01-01T00:00:00Z",
                        "application/last-activity": "2023-01-01T00:00:00Z",
                    }
                },
                {
                    "json": {
                        "application/id": 123,
                        "application/state": "submitted",
                        "application/accepted-licenses": {"test-user": [1]},
                        "application/first-submitted": "2023-01-01T12:00:00Z",
                        "application/applicant": {
                            "userid": "test-user",
                            "name": "Test User",
                            "email": "test@example.com",
                        },
                        "application/resources": [],
                        "application/forms": [],
                        "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                        "application/created": "2023-01-01T00:00:00Z",
                        "application/modified": "2023-01-01T12:00:00Z",
                        "application/last-activity": "2023-01-01T12:00:00Z",
                    }
                },
            ],
        )
        # Mock accept_license call
        m.post(
            f"{REMS_URL}/api/applications/accept-licenses",
            json={"success": True},
        )
        # Mock submit_application call
        m.post(
            f"{REMS_URL}/api/applications/submit",
            json={"success": True},
        )

        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        rems_form = self.rems_connector.get_form_for_catalogue_item(
            catalogue_item.form_id
        )
        # create application
        application_id = self.rems_connector.create_application([catalogue_item.id])
        # save draftFormTemplate
        self.rems_connector.save_application_draft(
            application_id, rems_form.id, {"fld1": "test"}
        )

        resource_id = catalogue_item.resource_id
        resource = self.rems_connector.get_resource(resource_id)
        licenses = resource.licenses
        license_ids = []
        for license in licenses:
            license_id = license.id
            license_ids.append(license_id)

        application = self.rems_connector.get_application(application_id)
        self.assertIsNone(application.first_submitted)

        self.rems_connector.accept_license(application_id, license_ids)
        self.rems_connector.submit_application(application_id)

        application = self.rems_connector.get_application(application_id)
        self.assertIsNotNone(application.first_submitted)

    def test_my_applications(self, m):
        # Mock get_my_applications call
        m.get(
            f"{REMS_URL}/api/my-applications",
            json=[
                {
                    "application/id": 123,
                    "application/state": "application.state/submitted",
                    "application/accepted-licenses": {"test-user": [1]},
                    "application/first-submitted": "2023-01-01T12:00:00Z",
                    "application/applicant": {
                        "userid": "test-user",
                        "name": "Test User",
                        "email": "test@example.com",
                    },
                    "application/resources": [
                        {
                            "catalogue-item/id": 1,
                            "resource/ext-id": self.dataset_id,
                            "catalogue-item/title": {"en": "Test Dataset"},
                            "catalogue-item/infourl": {"en": "http://example.com"},
                            "catalogue-item/start": "2023-01-01T00:00:00Z",
                            "catalogue-item/end": None,
                            "catalogue-item/expired": False,
                            "catalogue-item/enabled": True,
                            "catalogue-item/archived": False,
                            "resource/id": 1,
                        }
                    ],
                    "application/forms": [],
                    "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                    "application/created": "2023-01-01T00:00:00Z",
                    "application/modified": "2023-01-01T12:00:00Z",
                    "application/last-activity": "2023-01-01T12:00:00Z",
                },
                {
                    "application/id": 124,
                    "application/state": "application.state/approved",
                    "application/accepted-licenses": {"test-user": [1, 2]},
                    "application/first-submitted": "2023-01-02T10:00:00Z",
                    "application/applicant": {
                        "userid": "test-user",
                        "name": "Test User",
                        "email": "test@example.com",
                    },
                    "application/resources": [
                        {
                            "catalogue-item/id": 2,
                            "resource/ext-id": "another-dataset",
                            "catalogue-item/title": {"en": "Another Dataset"},
                            "catalogue-item/infourl": {"en": "http://example.com"},
                            "catalogue-item/start": "2023-01-02T00:00:00Z",
                            "catalogue-item/end": None,
                            "catalogue-item/expired": False,
                            "catalogue-item/enabled": True,
                            "catalogue-item/archived": False,
                            "resource/id": 2,
                        }
                    ],
                    "application/forms": [],
                    "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                    "application/created": "2023-01-02T00:00:00Z",
                    "application/modified": "2023-01-02T15:00:00Z",
                    "application/last-activity": "2023-01-02T15:00:00Z",
                },
            ],
        )

        result = self.rems_connector.my_applications()
        self.assertIsNotNone(result)

    def test_applications(self, m):
        # Mock get_applications call
        m.get(
            f"{REMS_URL}/api/applications",
            json=[
                {
                    "application/id": 200,
                    "application/state": "application.state/submitted",
                    "application/accepted-licenses": {"user1": [1]},
                    "application/first-submitted": "2023-01-01T12:00:00Z",
                    "application/applicant": {
                        "userid": "user1",
                        "name": "User One",
                        "email": "user1@example.com",
                    },
                    "application/resources": [
                        {
                            "catalogue-item/id": 1,
                            "resource/ext-id": "dataset-123",
                            "catalogue-item/title": {"en": "Public Dataset"},
                            "catalogue-item/infourl": {"en": "http://example.com"},
                            "catalogue-item/start": "2023-01-01T00:00:00Z",
                            "catalogue-item/end": None,
                            "catalogue-item/expired": False,
                            "catalogue-item/enabled": True,
                            "catalogue-item/archived": False,
                            "resource/id": 1,
                        }
                    ],
                    "application/forms": [],
                    "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                    "application/created": "2023-01-01T00:00:00Z",
                    "application/modified": "2023-01-01T12:00:00Z",
                    "application/last-activity": "2023-01-01T12:00:00Z",
                },
                {
                    "application/id": 201,
                    "application/state": "application.state/approved",
                    "application/accepted-licenses": {"user2": [1, 2]},
                    "application/first-submitted": "2023-01-02T10:00:00Z",
                    "application/applicant": {
                        "userid": "user2",
                        "name": "User Two",
                        "email": "user2@example.com",
                    },
                    "application/resources": [
                        {
                            "catalogue-item/id": 2,
                            "resource/ext-id": "dataset-456",
                            "catalogue-item/title": {"en": "Research Dataset"},
                            "catalogue-item/infourl": {"en": "http://example.com"},
                            "catalogue-item/start": "2023-01-02T00:00:00Z",
                            "catalogue-item/end": None,
                            "catalogue-item/expired": False,
                            "catalogue-item/enabled": True,
                            "catalogue-item/archived": False,
                            "resource/id": 2,
                        }
                    ],
                    "application/forms": [],
                    "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                    "application/created": "2023-01-02T00:00:00Z",
                    "application/modified": "2023-01-02T15:00:00Z",
                    "application/last-activity": "2023-01-02T15:00:00Z",
                },
                {
                    "application/id": 202,
                    "application/state": "application.state/draft",
                    "application/accepted-licenses": {},
                    "application/applicant": {
                        "userid": "user3",
                        "name": "User Three",
                        "email": "user3@example.com",
                    },
                    "application/resources": [
                        {
                            "catalogue-item/id": 3,
                            "resource/ext-id": "dataset-789",
                            "catalogue-item/title": {"en": "Clinical Dataset"},
                            "catalogue-item/infourl": {"en": "http://example.com"},
                            "catalogue-item/start": "2023-01-03T00:00:00Z",
                            "catalogue-item/end": None,
                            "catalogue-item/expired": False,
                            "catalogue-item/enabled": True,
                            "catalogue-item/archived": False,
                            "resource/id": 3,
                        }
                    ],
                    "application/forms": [],
                    "application/workflow": {"workflow/id": REMS_WORKFLOW_ID},
                    "application/created": "2023-01-03T00:00:00Z",
                    "application/modified": "2023-01-03T08:00:00Z",
                    "application/last-activity": "2023-01-03T08:00:00Z",
                },
            ],
        )

        applications = self.rems_connector.applications("")
        self.assertIsNotNone(applications)

    def test_create_user(self, m):
        # Mock create_user call
        m.post(f"{REMS_URL}/api/users/create", json={"success": True}, status_code=200)

        response = self.rems_connector.create_user(
            REMS_API_USER, "test", "test@lcsb.lu"
        )
        self.assertTrue(response)

    def test_add_attachment(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )
        # Mock add_attachment call
        m.post(
            f"{REMS_URL}/api/applications/add-attachment",
            json={"success": True, "id": 456},
        )

        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        open(path.join(self.test_dir, "test.pdf"), "w").close()
        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        application_id = self.rems_connector.create_application([catalogue_item.id])
        response_id = self.rems_connector.add_attachment(
            application_id, path.join(self.test_dir, "test.pdf")
        )
        self.assertIsNotNone(response_id)

        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_save_application_draft_with_file_attachment(self, m):
        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(f"{REMS_URL}/api/resources/create", json={"success": True, "id": 1})
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        # Mock edit_catalogue_items call
        m.put(
            f"{REMS_URL}/api/catalogue-items/edit",
            json={"success": True},
        )
        # Mock get_catalogue_item calls
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[
                {
                    "id": 1,
                    "resid": self.dataset_id,
                    "formid": 3,
                    "wfid": REMS_WORKFLOW_ID,
                    "resource-id": 1,
                    "archived": False,
                    "localizations": {"en": {"title": "Test Dataset"}},
                    "start": "2023-01-01T00:00:00Z",
                    "organization": {"organization/id": "test-org"},
                    "expired": False,
                    "end": None,
                    "enabled": True,
                }
            ],
        )
        # Mock get_form call with attachment field
        m.get(
            f"{REMS_URL}/api/forms/3",
            json={
                "form/id": 3,
                "archived": False,
                "enabled": True,
                "organization": {
                    "organization/id": "test-org",
                    "organization/short-name": {"en": "Test Org"},
                    "organization/name": {"en": "Test Organization"},
                },
                "form/fields": [
                    {
                        "field/id": "field1",
                        "field/type": "text",
                        "field/title": {"en": "Text Field"},
                        "field/optional": False,
                    },
                    {
                        "field/id": "attachment1",
                        "field/type": "attachment",
                        "field/title": {"en": "Attachment Field"},
                        "field/optional": True,
                    },
                ],
            },
        )
        # Mock create_application call
        m.post(
            f"{REMS_URL}/api/applications/create",
            json={"success": True, "application-id": 123},
        )
        # Mock add_attachment call
        m.post(
            f"{REMS_URL}/api/applications/add-attachment",
            json={"success": True, "id": 456},
        )
        # Mock save_application_draft call
        m.post(
            f"{REMS_URL}/api/applications/save-draft",
            json={"success": True},
        )

        # Execute the test
        self.rems_connector.export_entities([self.dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(self.dataset)
        rems_form = self.rems_connector.get_form_for_catalogue_item(
            catalogue_item.form_id
        )
        field_values = {}

        # Create application
        application_id = self.rems_connector.create_application([catalogue_item.id])

        # Create a mock file for testing
        test_file_content = b"This is test file content"
        mock_file = FileStorage(
            stream=BytesIO(test_file_content),
            filename="test_file.pdf",
            content_type="application/pdf",
        )

        # Mock the request.files to simulate file upload
        mock_files = {}

        for field in rems_form.fields:
            rems_field_id = field.fieldid
            wtf_field = FieldBuilder.build_field_builder(field)

            # Check if this is an attachment field
            if field.fieldtype == "attachment":
                # Mock the request.files for this field
                mock_files[rems_field_id] = mock_file

                # Patch request.files during transform_value call
                with patch(
                    "datacatalog.acces_handler.rems_handler.request"
                ) as mock_request:
                    mock_request.files = mock_files
                    field_values[rems_field_id] = wtf_field.transform_value(
                        None, self.rems_connector, application_id
                    )
            else:
                # For non-attachment fields, use regular test value
                flask_form_value = "test"
                field_values[rems_field_id] = wtf_field.transform_value(
                    flask_form_value, self.rems_connector, application_id
                )

        # Save draft
        response = self.rems_connector.save_application_draft(
            application_id, rems_form.id, field_values
        )

        self.assertTrue(response)
