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
    FormField,
    FormTemplateFieldsOptions,
    OrganizationOverview,
)
from tests.base_test import BaseTest

__author__ = "Nirmeen Sallam"


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
            app.config.get("REMS_API_USER"),
            app.config.get("REMS_API_KEY"),
            app.config.get("REMS_URL"),
            app.config.get("REMS_WORKFLOW_ID"),
            app.config.get("REMS_VERIFY_SSL"),
        )
        self.rems_access_handler.rems_connector.organization_id = app.config.get(
            "REMS_ORGANIZATION_ID"
        )
        self.rems_access_handler.rems_connector.licenses = app.config.get(
            "REMS_LICENSES"
        )

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
                    "user_id": app.config.get("REMS_API_USER"),
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
                    "user_id": app.config.get("REMS_API_USER"),
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

    def test_my_applications(self):
        result = self.rems_access_handler.my_applications()
        self.assertIsNotNone(result)

    def test_apply_and_has_access_submitted_application(self):
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

    def test_get_datasets(self):
        pass

    def test_create_form(self):
        self.rems_access_handler.rems_connector.export_entities([self.dataset])
        form_data = ImmutableMultiDict(
            [
                ("fld1", "test"),
                ("license_2", "on"),
                ("submit", "Send"),
                ("csrf_token", "test"),
            ]
        )
        self.rems_access_handler.rems_connector.get_form_for_catalogue_item = (
            MagicMock()
        )
        fields = [
            # string
            FormField(
                **{
                    "field/id": "text",
                    "field/type": "text",
                    "field/title": {"en": "field1"},
                    "field/optional": False,
                    "field/max_length": 10,
                    "field/placeholder": {"en": "placeholder1"},
                }
            ),
            # label
            FormField(
                **{
                    "field/id": "label",
                    "field/type": "label",
                    "field/title": {"en": "field2"},
                    "field/optional": True,
                    "field/max_length": 10,
                    "field/placeholder": {"en": "placeholder2"},
                }
            ),
            # header
            FormField(
                **{
                    "field/id": "header",
                    "field/type": "header",
                    "field/title": {"en": "field3"},
                    "field/optional": False,
                }
            ),
            # textarea
            FormField(
                **{
                    "field/id": "texta",
                    "field/type": "texta",
                    "field/title": {"en": "field4"},
                    "field/optional": False,
                }
            ),
            # attachment
            FormField(
                **{
                    "field/id": "attachment",
                    "field/type": "attachment",
                    "field/title": {"en": "field5"},
                    "field/optional": False,
                }
            ),
            # date
            FormField(
                **{
                    "field/id": "date",
                    "field/type": "date",
                    "field/title": {"en": "field6"},
                    "field/optional": False,
                }
            ),
            # select
            FormField.model_validate(
                {
                    "field/id": "option",
                    "field/type": "option",
                    "field/title": {"en": "field7"},
                    "field/optional": False,
                    "field/options": [
                        FormTemplateFieldsOptions(key="1", label={"en": "test"})
                    ],
                }
            ),
            # multiselect
            FormField.model_validate(
                {
                    "field/id": "multiselect",
                    "field/type": "multiselect",
                    "field/title": {"en": "field8"},
                    "field/optional": False,
                    "field/options": [
                        FormTemplateFieldsOptions(key="2", label={"en": "test2"})
                    ],
                }
            ),
            # email
            FormField(
                **{
                    "field/id": "email",
                    "field/type": "email",
                    "field/title": {"en": "field6"},
                    "field/optional": False,
                }
            ),
        ]
        organization = OrganizationOverview.model_validate(
            {
                "organization/id": self.rems_access_handler.rems_connector.organization_id,
                "organization/short_name": {"en": "text in English"},
                "organization/name": {"en": "text in English"},
            }
        )
        form = Form.model_validate(
            {
                "form/id": 6,
                "organization": organization,
                "form/internal-name": "test",
                "form/title": "form",
                "form/fields": fields,
                "enabled": True,
                "form/external-title": {"en": "text in English"},
                "archived": False,
            }
        )
        self.rems_access_handler.rems_connector.get_form_for_catalogue_item.return_value = (
            form
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
