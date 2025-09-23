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

import requests_mock

from datacatalog import app
from datacatalog.connector.rems_connector import RemsConnector
from datacatalog.exporter.entities_exporter import EntitiesExporter
from datacatalog.models.dataset import Dataset
from datacatalog.connector.rems_connector import CatalogueItemDoesntExistException

from tests.base_test import BaseTest

__author__ = "Nirmeen Sallam"


REMS_URL = app.config.get("REMS_URL", "http://rems-mock-host")
REMS_API_USER = app.config.get("REMS_API_USER", "test-api-user")
REMS_API_KEY = app.config.get("REMS_API_KEY", "test-api-key")
REMS_WORKFLOW_ID = app.config.get("REMS_WORKFLOW_ID", 3)
REMS_ORGANIZATION_ID = app.config.get(
    "REMS_ORGANIZATION_ID", "89fca267-693e-41e1-830b-b4e6326c1dd0"
)
REMS_LICENSES = app.config.get("REMS_LICENSES", [1, 2])


@requests_mock.Mocker()
class TestEntitiesExporter(BaseTest):
    def setUp(self):
        self.rems_connector = RemsConnector(
            api_username=REMS_API_USER,
            api_key=REMS_API_KEY,
            host=REMS_URL,
            workflow_id=REMS_WORKFLOW_ID,
            organization_id=REMS_ORGANIZATION_ID,
            licenses=REMS_LICENSES,
            verify_ssl=False,
        )

    def test_entities_exporter(self, m):
        title = "Great dataset!"
        dataset = Dataset(title)
        dataset.e2e = True
        dataset.form_id = 3

        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(
            f"{REMS_URL}/api/resources/create",
            json={"success": True, "id": 1},
        )
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        m.put(f"{REMS_URL}/api/catalogue-items/edit", json={"success": True})
        # Mock get_catalogue_item call
        catalogue_item_data = {
            "id": 1,
            "resid": dataset.id,
            "formid": 3,
            "wfid": 5,
            "resource-id": 1,
            "archived": False,
            "localizations": {"en": {"title": "Test Dataset"}},
            "start": "2023-01-01T00:00:00Z",
            "organization": {"organization/id": "test-org"},
            "expired": False,
            "end": None,
            "enabled": True,
        }
        # Mock catalogue-items endpoint
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[catalogue_item_data],
        )

        exporter = EntitiesExporter([self.rems_connector])
        exporter.export_all([dataset])
        catalogue_item = self.rems_connector.get_catalogue_item(dataset)
        self.assertEqual(catalogue_item.resid, dataset.id)

    def test_entities_exporter_dataset_form_id_none(self, m):
        title = "Great dataset!"
        dataset = Dataset(title)
        dataset.e2e = True
        dataset.form_id = None

        # Mock export_entities calls
        m.get(f"{REMS_URL}/api/resources", json=[])
        m.post(
            f"{REMS_URL}/api/resources/create",
            json={"success": True, "id": 1},
        )
        m.post(
            f"{REMS_URL}/api/catalogue-items/create",
            json={"success": True, "id": 1},
        )
        m.put(f"{REMS_URL}/api/catalogue-items/edit", json={"success": True})
        # Mock get_catalogue_item call to return empty list
        m.get(f"{REMS_URL}/api/catalogue-items", json=[])

        exporter = EntitiesExporter([self.rems_connector])
        exporter.export_all([dataset])
        self.assertRaises(
            CatalogueItemDoesntExistException,
            self.rems_connector.get_catalogue_item,
            dataset,
        )
