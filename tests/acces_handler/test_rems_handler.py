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

import datetime
from unittest.mock import MagicMock

from flask_login import current_user
from flask_wtf import FlaskForm
import requests_mock
from werkzeug.datastructures import ImmutableMultiDict
from wtforms import (
    StringField,
    TextAreaField,
    FileField,
    DateField,
    SelectField,
    SelectMultipleField,
)
from wtforms.fields.html5 import EmailField

from datacatalog import app
from datacatalog.acces_handler.access_handler import ApplicationState
from datacatalog.acces_handler.rems_handler import RemsAccessHandler
from datacatalog.models.dataset import Dataset
from datacatalog.connector.rems_client import (
    Form,
    CatalogueItem,
    Resource,
    ResourceLicense,
)
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
REMS_VERIFY_SSL = False


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class TestRemsAccessHandler(BaseTest):
    def setUp(self):
        self.assertTrue(self.app.testing)
        title = "Great dataset!"
        self.dataset = Dataset(title)
        self.dataset.e2e = True
        self.dataset.form_id = 3
        self.dataset_id = self.dataset.id

        self.rems_access_handler = RemsAccessHandler(
            current_user,
            REMS_API_USER,
            REMS_API_KEY,
            REMS_URL,
            REMS_WORKFLOW_ID,
            REMS_VERIFY_SSL,
        )
        self.rems_access_handler.rems_connector.organization_id = REMS_ORGANIZATION_ID
        self.rems_access_handler.rems_connector.licenses = REMS_LICENSES

    def test_requires_logged_in_user(self):
        self.assertTrue(self.rems_access_handler.requires_logged_in_user(self.dataset))

    def test_supports_listing_accesses(self):
        self.assertTrue(self.rems_access_handler.supports_listing_accesses())

    def test_has_access_application_none(self):
        self.rems_access_handler.rems_connector.applications = MagicMock()
        self.rems_access_handler.rems_connector.applications.return_value = []
        result = self.rems_access_handler.has_access(self.dataset)
        self.assertFalse(result)

    def test_has_access_application_userid_not_equal_api_username(self):
        applications = [
            {
                "applicant": {
                    "email": "test@lcsb.lu",
                    "name": "test",
                    "notification_email": None,
                    "organization": None,
                    "user_id": "test",
                },
                "first_submitted": None,
                "state": "application.state/draft",
            }
        ]

        applications[0] = dotdict(applications[0])
        applications[0].applicant = dotdict(applications[0].applicant)

        self.rems_access_handler.rems_connector.applications = MagicMock()
        self.rems_access_handler.rems_connector.applications.return_value = applications
        result = self.rems_access_handler.has_access(self.dataset)
        self.assertFalse(result)

    def test_has_access_application_approved(self):
        applications = [
            {
                "applicant": {
                    "email": "test@lcsb.lu",
                    "name": "test",
                    "notification_email": None,
                    "organization": None,
                    "user_id": REMS_API_USER,
                },
                "first_submitted": None,
                "state": "application.state/approved",
            }
        ]

        applications[0] = dotdict(applications[0])
        applications[0].applicant = dotdict(applications[0].applicant)

        self.rems_access_handler.rems_connector.applications = MagicMock()
        self.rems_access_handler.rems_connector.applications.return_value = applications
        result = self.rems_access_handler.has_access(self.dataset)
        self.assertEqual(result.value, ApplicationState.approved.value)

    def test_has_access_application_draft(self):
        applications = [
            {
                "applicant": {
                    "email": "test@lcsb.lu",
                    "name": "test",
                    "notification_email": None,
                    "organization": None,
                    "user_id": REMS_API_USER,
                },
                "first_submitted": None,
                "state": "application.state/draft",
            }
        ]

        applications[0] = dotdict(applications[0])
        applications[0].applicant = dotdict(applications[0].applicant)

        self.rems_access_handler.rems_connector.applications = MagicMock()
        self.rems_access_handler.rems_connector.applications.return_value = applications
        result = self.rems_access_handler.has_access(self.dataset)
        self.assertFalse(result)

    @requests_mock.Mocker()
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
        result = self.rems_access_handler.my_applications()
        self.assertIsNotNone(result)

    @requests_mock.Mocker()
    def test_apply_and_has_access_submitted_application(self, m):
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
        catalogue_item = CatalogueItem(
            id=1,
            resid=self.dataset_id,
            **{"formid": 3},
            wfid=REMS_WORKFLOW_ID,
            **{"resource-id": 1},
            archived=False,
            localizations={"en": {"title": "Test Dataset"}},
            start="2023-01-01T00:00:00Z",
            organization={"organization/id": "test-org"},
            expired=False,
            end=None,
            enabled=True,
        )
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[catalogue_item.model_dump(by_alias=True)],
        )
        # Mock get_form call
        form_field_data = {
            "field/id": "fld1",
            "field/type": "text",
            "field/title": {"en": "Test Field"},
            "field/optional": False,
        }
        form = Form(
            **{"form/id": 3},
            **{"form/internal-name": "test-form"},
            **{"form/title": "Test Form"},
            **{"form/external-title": {"en": "Test Form Title"}},
            archived=False,
            enabled=True,
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            **{"form/fields": [form_field_data]},
        )
        m.get(
            f"{REMS_URL}/api/forms/3",
            json=form.model_dump(by_alias=True),
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
        resource_license = ResourceLicense(
            id=2,
            licensetype="license",
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            enabled=True,
            archived=False,
            localizations={
                "en": {
                    "title": "Test License",
                    "textcontent": "This is the license text content",
                }
            },
        )
        resource = Resource(
            id=1,
            resid=self.dataset_id,
            enabled=True,
            archived=False,
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            licenses=[resource_license],
            **{"resource/duo": {}},
        )
        m.get(
            f"{REMS_URL}/api/resources/1",
            json=resource.model_dump(by_alias=True),
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
        # Mock applications call (for has_access check)
        m.get(
            f"{REMS_URL}/api/applications",
            json=[
                {
                    "application/id": 123,
                    "application/state": "application.state/submitted",
                    "application/accepted-licenses": {"test-user": [2]},
                    "application/first-submitted": "2023-01-01T12:00:00Z",
                    "application/applicant": {
                        "userid": REMS_API_USER,
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
                }
            ],
        )

        self.rems_access_handler.rems_connector.export_entities([self.dataset])
        form_data = ImmutableMultiDict(
            [
                ("fld1", "test"),
                ("license_2", "on"),
                ("submit", "Send"),
                ("csrf_token", "test"),
            ]
        )
        form = self.rems_access_handler.create_form(self.dataset, form_data)
        self.rems_access_handler.apply(self.dataset, form)

        result = self.rems_access_handler.has_access(self.dataset)
        self.assertEqual(result.value, ApplicationState.submitted.value)

    @requests_mock.Mocker()
    def test_create_form(self, m):
        # Mock get_catalogue_item calls
        catalogue_item = CatalogueItem(
            id=1,
            resid=self.dataset_id,
            **{"formid": 3},
            wfid=REMS_WORKFLOW_ID,
            **{"resource-id": 1},
            archived=False,
            localizations={"en": {"title": "Test Dataset"}},
            start="2023-01-01T00:00:00Z",
            organization={"organization/id": "test-org"},
            expired=False,
            end=None,
            enabled=True,
        )
        m.get(
            f"{REMS_URL}/api/catalogue-items",
            json=[catalogue_item.model_dump(by_alias=True)],
        )
        # Mock get_resource call
        resource_license = ResourceLicense(
            id=2,
            licensetype="license",
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            enabled=True,
            archived=False,
            localizations={
                "en": {
                    "title": "Test License",
                    "textcontent": "This is the license text content",
                }
            },
        )
        resource = Resource(
            id=1,
            resid=self.dataset_id,
            enabled=True,
            archived=False,
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            licenses=[resource_license],
            **{"resource/duo": {}},
        )
        m.get(
            f"{REMS_URL}/api/resources/1",
            json=resource.model_dump(by_alias=True),
        )
        # Mock get_form call
        form_fields_data = [
            {
                "field/id": "text",
                "field/type": "text",
                "field/title": {"en": "field1"},
                "field/optional": False,
                "field/max-length": 10,
                "field/placeholder": {"en": "placeholder1"},
            },
            {
                "field/id": "label",
                "field/type": "label",
                "field/title": {"en": "field2"},
                "field/optional": True,
                "field/max-length": 10,
                "field/placeholder": {"en": "placeholder2"},
            },
            {
                "field/id": "header",
                "field/type": "header",
                "field/title": {"en": "field3"},
                "field/optional": False,
            },
            {
                "field/id": "texta",
                "field/type": "texta",
                "field/title": {"en": "field4"},
                "field/optional": False,
            },
            {
                "field/id": "attachment",
                "field/type": "attachment",
                "field/title": {"en": "field5"},
                "field/optional": False,
            },
            {
                "field/id": "date",
                "field/type": "date",
                "field/title": {"en": "field6"},
                "field/optional": False,
            },
            {
                "field/id": "option",
                "field/type": "option",
                "field/title": {"en": "field7"},
                "field/optional": False,
                "field/options": [{"key": "1", "label": {"en": "test"}}],
            },
            {
                "field/id": "multiselect",
                "field/type": "multiselect",
                "field/title": {"en": "field8"},
                "field/optional": False,
                "field/options": [{"key": "2", "label": {"en": "test2"}}],
            },
            {
                "field/id": "email",
                "field/type": "email",
                "field/title": {"en": "field9"},
                "field/optional": False,
            },
        ]
        form = Form(
            **{"form/id": 3},
            **{"form/internal-name": "test-form"},
            **{"form/title": "Test Form"},
            **{"form/external-title": {"en": "Test Form Title"}},
            archived=False,
            enabled=True,
            organization={
                "organization/id": "test-org",
                "organization/short-name": {"en": "Test Org"},
                "organization/name": {"en": "Test Organization"},
            },
            **{"form/fields": form_fields_data},
        )
        m.get(
            f"{REMS_URL}/api/forms/3",
            json=form.model_dump(by_alias=True),
        )

        form_data = ImmutableMultiDict(
            [
                ("fld1", "test"),
                ("license_2", "on"),
                ("submit", "Send"),
                ("csrf_token", "test"),
            ]
        )

        result = self.rems_access_handler.create_form(self.dataset, form_data)
        self.assertEqual("FormClass", type(result).__name__)
        self.assertIsInstance(result, FlaskForm)
        self.assertIsInstance(result.text, StringField)
        self.assertIsInstance(result.label, StringField)
        self.assertIsInstance(result.header, StringField)
        self.assertIsInstance(result.texta, TextAreaField)
        self.assertIsInstance(result.attachment, FileField)
        self.assertIsInstance(result.date, DateField)
        self.assertIsInstance(result.option, SelectField)
        self.assertIsInstance(result.multiselect, SelectMultipleField)
        self.assertIsInstance(result.email, EmailField)

    def test_build_application(self):
        application = {
            "state": "application.state/draft",
            "created": datetime.datetime.now().isoformat(),
            "resources": [
                {
                    "title": {"en": "Great dataset!"},
                    "ext_id": "224b4550-9386-11eb-b0ff-acde48001122",
                }
            ],
            "applicant": {"user_id": "test"},
        }
        application = dotdict(application)
        application.resources[0] = dotdict(application.resources[0])
        application.applicant = dotdict(application.applicant)

        built_application = RemsAccessHandler.build_application(application)
        self.assertEqual(built_application.state.value, "draft")

    def test_build_application_state_value_error(self):
        application = {
            "state": "application.state/test_state_error",
            "created": datetime.datetime.now().isoformat(),
            "resources": [
                {
                    "title": {"en": "Great dataset!"},
                    "ext_id": "224b4550-9386-11eb-b0ff-acde48001122",
                }
            ],
            "applicant": {"user_id": "test"},
        }
        application = dotdict(application)
        application.resources[0] = dotdict(application.resources[0])
        application.applicant = dotdict(application.applicant)

        built_application = RemsAccessHandler.build_application(application)
        self.assertIsNone(built_application.state)
