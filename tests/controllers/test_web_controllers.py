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

import os
import re
import shutil
import tempfile
import unittest
from os import path
from unittest.mock import MagicMock, patch

from flask import url_for
import requests_mock

import datacatalog
from datacatalog import app
from datacatalog.connector.dats_connector import DATSConnector
from datacatalog.connector.geostudies_connector import GEOStudiesConnector
from datacatalog.connector.json_connector import JSONConnector
from datacatalog.controllers.web_controllers import (
    make_key,
    csrf_error,
    authentication_errors,
    page_not_found,
    get_entity,
)
from datacatalog.exceptions import AuthenticationException
from datacatalog.importer.entities_importer import EntitiesImporter
from datacatalog.models.dataset import Dataset
from datacatalog.models.project import Project
from datacatalog.models.study import Study
from datacatalog.models.user import User
from datacatalog.acces_handler.access_handler import Application
from tests.base_test import BaseTest, get_resource_path, get_clean_html_body

__author__ = "Nirmeen Sallam"

REMS_URL = app.config.get("REMS_URL", "http://rems-mock-host")


class TestWebControllers(BaseTest):
    connector = [
        JSONConnector(os.path.join(get_resource_path("records.json")), Dataset),
        GEOStudiesConnector(get_resource_path("geo_studies_test"), Study),
        DATSConnector(get_resource_path("imi_projects_test"), Project),
    ]
    entities_importer = EntitiesImporter(connector)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.solr_orm = app.config["_solr_orm"]
        cls.solr_orm.delete_fields()
        cls.solr_orm.create_fields()

    def setUp(self):
        self.solr_orm.delete(query="*:*")
        self.entities_importer.import_all()
        self.dataset_length = len(list(Dataset.query.all()))
        self.project_length = len(list(Project.query.all()))
        self.study_length = len(list(Study.query.all()))

    def test_make_key(self):
        self.assertIsNotNone(make_key())

    def test_csrf_error(self):
        response = csrf_error("CSRF validation failed.")
        self.assertIn("Error 400 - CSRF validation failed.", response[0])

    def test_authentication_errors(self):
        response = authentication_errors(AuthenticationException("Invalid Credentials"))
        self.assertIn("Invalid Credentials", response[0])

    def test_page_not_found(self):
        response = page_not_found(Exception("Page not found"))
        self.assertIn("Page not found", response[0])

    def test_entities_search(self):
        with self.client as client:
            entities = client.get("/datasets")
            self.assertIn(
                f"{self.dataset_length} datasets found",
                re.sub(r"\s+", " ", entities.data.decode("utf-8")),
            )

    def test_home(self):
        with self.client as client:
            landing_page = client.get("/")
            self.assertEqual(landing_page.status_code, 200)
            landing_cleantext = get_clean_html_body(landing_page)
            self.assertIn("Data Catalog - Home", landing_cleantext)
            self.assertIn(f"Datasets {self.dataset_length}", landing_cleantext)
            self.assertIn(f"Projects {self.project_length}", landing_cleantext)
            self.assertIn(f"Studies {self.study_length}", landing_cleantext)

    def test_no_landing(self):
        with app.app_context():
            app.config["NO_LANDING"] = True
        with self.client as client:
            landing_page = client.get("/")
        landing_cleantext = get_clean_html_body(landing_page)
        self.assertIn("Data Catalog - Home", landing_page.data.decode("utf-8"))
        self.assertIn(
            f"{self.dataset_length} datasets found",
            landing_cleantext,
        )

    def test_search(self):
        with self.client as client:
            search_result = client.get("/search")
            search_result_clean_text = get_clean_html_body(search_result)
            self.assertIn("Data Catalog - Home", search_result.data.decode("utf-8"))
            self.assertIn(
                f"{self.dataset_length} datasets found",
                search_result_clean_text,
            )

    def test_search_query_sort_order(self):
        with self.client as client:
            search_result_desc = client.get("/search?query=med&sort_by=&order=desc")
            search_result_asc = client.get("/search?query=med&sort_by=&order=asc")
            self.assertIn(
                "Data Catalog - Home", search_result_desc.data.decode("utf-8")
            )
            self.assertIn("search-results", search_result_desc.data.decode("utf-8"))
            self.assertIn("search-results", search_result_asc.data.decode("utf-8"))

    def test_entity_details(self):
        datasets = list(Dataset.query.all())
        with self.client as client:
            entity = client.get(
                url_for(
                    "entity_details",
                    entity_name="dataset",
                    entity_id=datasets[0].id,
                )
            )
        entity_clean_text = get_clean_html_body(entity)
        self.assertIn(datasets[0].title, entity_clean_text)

    def test_entity_by_slug(self):
        dataset = Dataset.query.get("d6ab9395-1ae3-453b-aa0e-c1de613905d8")
        with self.client as client:
            response = client.get(
                url_for(
                    "entity_by_slug", entity_name="dataset", slug_name="precisesads"
                ),
                follow_redirects=False,
            )
        self.assertEqual(301, response.status_code)
        expected_redirected_location = url_for(
            "entity_details",
            entity_name="dataset",
            entity_id=dataset.id,
            _external=True,
        )
        self.assertIn(response.location, expected_redirected_location)

    def test_entity_by_slug_projects(self):
        project = Project.query.get("dc9970e8-147a-11eb-b51f-8c8590c45a21")
        self.assertEqual(1, len(project.slugs))
        expected_redirected_location = url_for(
            "entity_details",
            entity_name="project",
            entity_id=project.id,
            _external=True,
        )
        with self.client as client:
            for slug in project.slugs:
                response = client.get(
                    url_for("entity_by_slug", entity_name="project", slug_name=slug),
                    follow_redirects=False,
                )
                self.assertEqual(301, response.status_code)
                self.assertIn(response.location, expected_redirected_location)

    def test_entity_by_slug_not_found(self):
        with self.client as client:
            response = client.get(
                url_for("entity_by_slug", entity_name="dataset", slug_name="not_found"),
                follow_redirects=False,
            )
        self.assertEqual(404, response.status_code)

    def test_entity_by_slug_invalid_entity_name(self):
        with self.client as client:
            response = client.get(
                url_for("entity_by_slug", entity_name="test", slug_name="not_found"),
                follow_redirects=False,
            )
        self.assertEqual(404, response.status_code)

    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_entity_details_authenticated_user(self, current_user, m):
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )

        user = User("test", "test", "test")
        datasets = list(Dataset.query.all())
        first_dataset = datasets[0]
        current_user.return_value = user
        client = app.test_client()

        entity = client.get(f"/e/dataset/{first_dataset.id}")
        entity_clean_text = get_clean_html_body(entity)
        self.assertIn(first_dataset.title, entity_clean_text)
        self.assertNotIn("contact our data stewards", entity_clean_text)

    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_entity_details_authenticated_user_access_no_storages(
        self, current_user, m
    ):
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )
        m.get(
            f"{REMS_URL}/api/applications",
            json=[],
            status_code=200,
            real_http=False,
        )

        app.config["ACCESS_HANDLERS"] = {"dataset": "RemsOidc"}
        user = User("test", "test", "test")
        datasets = list(Dataset.query.all())
        first_dataset = datasets[0]
        user.accesses = [first_dataset.id]
        first_dataset.e2e = True
        first_dataset.storages = []
        first_dataset.save(commit=True)
        current_user.return_value = user
        client = app.test_client()

        entity = client.get(f"/e/dataset/{first_dataset.id}")
        entity_clean_text = get_clean_html_body(entity)
        self.assertIn(first_dataset.title, entity_clean_text)
        self.assertIn("contact our data stewards", entity_clean_text)

    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_entity_details_authenticated_user_access_storages(self, current_user, m):
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )
        m.get(
            f"{REMS_URL}/api/applications",
            json=[],
            status_code=200,
            real_http=False,
        )

        app.config["ACCESS_HANDLERS"] = {"dataset": "RemsOidc"}
        user = User("test", "test", "test")
        datasets = list(Dataset.query.all())
        first_dataset = datasets[0]
        user.accesses = [first_dataset.id]
        first_dataset.e2e = True
        first_dataset.storages = [
            {"location": "here", "platform": "Application/SW Platform"}
        ]
        first_dataset.save(commit=True)
        current_user.return_value = user
        client = app.test_client()
        entity = client.get(f"/e/dataset/{first_dataset.id}")
        entity_clean_text = get_clean_html_body(entity)
        self.assertIn(first_dataset.title, entity_clean_text)
        self.assertNotIn("contact our data stewards", entity_clean_text)

    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_entity_details_authenticated_user_access_no_known_storage(
        self, current_user, m
    ):
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )
        m.get(
            f"{REMS_URL}/api/applications",
            json=[],
            status_code=200,
            real_http=False,
        )

        app.config["ACCESS_HANDLERS"] = {"dataset": "RemsOidc"}
        user = User("test", "test", "test")
        datasets = list(Dataset.query.all())
        first_dataset = datasets[0]
        user.accesses = [first_dataset.id]
        first_dataset.e2e = True
        first_dataset.storages = [{"location": "here", "platform": "link"}]
        first_dataset.save(commit=True)
        current_user.return_value = user
        client = app.test_client()
        entity = client.get(f"/e/dataset/{first_dataset.id}")
        entity_clean_text = get_clean_html_body(entity)
        self.assertIn(first_dataset.title, entity_clean_text)
        self.assertIn("contact our data stewards", entity_clean_text)

    def test_entity_details_project_deprecated_datasets(self):
        project = Project.query.get("dc9970e8-147a-11eb-b51f-8c8590c45a21")
        self.assertIsNotNone(project)

        active_dataset = Dataset("Active Test Dataset")
        active_dataset.deprecated = "Active"
        active_dataset.save()

        deprecated_dataset = Dataset("Deprecated Test Dataset")
        deprecated_dataset.deprecated = "Deprecated"
        deprecated_dataset.save()

        study = Study("Test Study")
        study.datasets = [active_dataset.id, deprecated_dataset.id]
        study.save()

        project.studies = [study.id]
        project.save()
        self.solr_orm.commit()

        with self.client as client:
            # Test default behavior (hide deprecated)
            response = client.get(f"/e/project/{project.id}")
            text = get_clean_html_body(response)
            self.assertIn("Active Test Dataset", text)
            self.assertNotIn("Deprecated Test Dataset", text)

            # Test with show_deprecated=true
            response = client.get(f"/e/project/{project.id}?show_deprecated=true")
            text = get_clean_html_body(response)
            self.assertIn("Active Test Dataset", text)
            self.assertIn("Deprecated Test Dataset", text)

    def test_get_entity(self):
        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            entity = get_entity("dataset", datasets[0].id)
            self.assertEqual(datasets[0].title, entity.title)

    def test_about(self):
        with self.client as client:
            about_page = client.get("/about")
            self.assertIn("Data Catalog - About", about_page.data.decode("utf-8"))

    def test_help(self):
        with self.client as client:
            help_page = client.get("/help")
            self.assertIn("Data Catalog - Help", help_page.data.decode("utf-8"))

    def test_export_dats_entity(self):
        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            with self.client as client:
                export_response = client.get(
                    f"/export_dats_entity/dataset/{datasets[0].id}"
                )
                data = export_response.data.decode("utf-8")
                self.assertIn(datasets[0].id, data)

    def test_request_access_require_login(self):
        app.config["ACCESS_HANDLERS"] = {"dataset": "Rems"}
        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            with self.client as client:
                dataset = datasets[0]
                dataset.e2e = True
                dataset.save(commit=True)
                request_access_response = client.get(
                    url_for(
                        "request_access", entity_name="dataset", entity_id=dataset.id
                    )
                )
                self.assertIn(url_for("login"), request_access_response.location)

    @unittest.skip("rems request access not used in production")
    @patch("flask_login.utils._get_user")
    def test_request_access_get(self, current_user):
        user = User("test", "test", "test")
        current_user.return_value = user
        client = app.test_client()

        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            request_access_response = client.get(
                url_for(
                    "request_access", entity_name="dataset", entity_id=datasets[0].id
                )
            )
            cleanregex = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")
            request_access_response = re.sub(
                cleanregex, " ", request_access_response.data.decode("utf-8")
            )
            request_access_response = re.sub(r"\s+", " ", request_access_response)
            self.assertIn(
                f"Request access to {datasets[0].title}", request_access_response
            )

    def test_request_access_no_access_handler(self):
        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            app.config["ACCESS_HANDLERS"] = {"dataset": None}

            with self.client as client:
                datacatalog.get_access_handler = MagicMock()
                datacatalog.get_access_handler.return_value = {}
                request_access_response = client.get(
                    url_for(
                        "request_access",
                        entity_name="dataset",
                        entity_id=datasets[0].id,
                    )
                )
                self.assertIn(
                    "Error 400 - No compatible request handlers for this entity",
                    request_access_response.data.decode("utf-8"),
                )

    @unittest.skip("rems request access not used in production")
    @patch("flask_login.utils._get_user")
    def test_request_access_invalid_form(self, current_user):
        user = User("test", "test", "test")
        current_user.return_value = user
        client = app.test_client()

        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            request_access_response = client.post(
                url_for(
                    "request_access", entity_name="dataset", entity_id=datasets[0].id
                )
            )
            cleanregex = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")
            request_access_response = re.sub(
                cleanregex, " ", request_access_response.data.decode("utf-8")
            )
            request_access_response = re.sub(r"\s+", " ", request_access_response)
            self.assertIn(
                f"Request access to {datasets[0].title}", request_access_response
            )

    @unittest.skip("rems request access not used in production")
    @patch("flask_login.utils._get_user")
    def test_request_access_success(self, current_user):
        app.config["ACCESS_HANDLERS"] = {"dataset": "Rems"}
        user = User("test", "test", "test")
        current_user.return_value = user
        client = app.test_client()

        datasets = list(Dataset.query.all())
        if len(datasets) > 0:
            request_access_response = client.post(
                url_for(
                    "request_access", entity_name="dataset", entity_id=datasets[0].id
                ),
                data={"fld1": "test", "license_2": "on"},
            )
            self.assertRedirects(request_access_response, url_for("search"))

    def test_custom_static(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        app.config["CUSTOM_STATIC_PATH"] = self.test_dir

        filepath = path.join(self.test_dir, "test.pdf")
        with open(filepath, "w") as f:
            f.write("test_line")

        with self.client as client:
            url = "/static_plugin" + filepath + "/"
            response = client.get(url)
        self.assertEqual(response.status_code, 404)
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_my_applications(self, current_user, m):
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )
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
                            "resource/ext-id": "test-dataset-id",
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
                    "application/workflow": {"workflow/id": 3},
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
                    "application/workflow": {"workflow/id": 3},
                    "application/created": "2023-01-02T00:00:00Z",
                    "application/modified": "2023-01-02T15:00:00Z",
                    "application/last-activity": "2023-01-02T15:00:00Z",
                },
            ],
            status_code=200,
            real_http=False,
        )

        app.config["ACCESS_HANDLERS"] = {"dataset": "Rems"}
        user = User("test", "test", "test")
        current_user.return_value = user
        client = app.test_client()
        applications = client.get(url_for("my_applications", entity_name="dataset"))
        cleanrgex = re.compile("<.*?>")
        applications_cleantext = re.sub(
            cleanrgex, " ", applications.data.decode("utf-8")
        )
        applications_cleantext = re.sub(r"\s+", " ", applications_cleantext)
        self.assertIn("My data access requests", applications_cleantext)

    @patch("datacatalog.acces_handler.rems_handler.RemsAccessHandler.my_applications")
    @patch("flask_login.utils._get_user")
    @requests_mock.Mocker()
    def test_my_applications_none_state(self, current_user, my_applications, m):
        """
        Tests that unknown application states are handled gracefully by the `my-applications` web controller
        """
        m.real_http = True
        m.post(
            f"{REMS_URL}/api/users/create",
            json={"success": True},
            status_code=200,
            real_http=False,
        )

        app.config["ACCESS_HANDLERS"] = {"dataset": "Rems"}
        # Mocking the current user
        user = User("test", "test", "test")
        current_user.return_value = user

        # Mocking the list of applications
        app_id = "2023/1"
        mock_application = Application(
            application_id=app_id,
            state=None,
            entity_id=1,
            entity_title="Test dataset",
            creation_date="2023/09/01",
            applicant_id=user.id,
        )
        my_applications.return_value = [mock_application]

        client = app.test_client()
        with self.assertLogs(
            "datacatalog.controllers.web_controllers", level="ERROR"
        ) as logs:
            res = client.get(url_for("my_applications", entity_name="dataset"))
            self.assert200(res, "Page should load correctly")

            res_text = res.data.decode("utf-8")
            self.assertNotIn(app_id, res_text)
            self.assertIn("An error occurred while loading some applications", res_text)

        assert len(logs.output) == 1
        assert (
            "An error occurred while loading some applications: Unknown state retrieved"
            in logs.output[0]
        )

    def tearDown(self):
        app.config["_solr_orm"].delete(query="*:*")
        app.config["_solr_orm"].commit()
