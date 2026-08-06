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

# coding='utf-8'


import unittest
from unittest.mock import patch

from flask import url_for
from flask_login import AnonymousUserMixin

from tests.base_test import BaseTest
from datacatalog import app, mail
from datacatalog.acces_handler.email_handler import EmailAccessHandler
from datacatalog.models.dataset import Dataset
from datacatalog.models.user import User

app.testing = True


class TestAccessRequest(BaseTest):
    TESTING = True

    def setUp(self):
        self.assertTrue(self.app.testing)
        self.solr_orm = app.config["_solr_orm"]
        self.solr_orm.delete(query="*:*")
        self.solr_orm.delete_fields()
        self.solr_orm.create_fields()
        title = "Great dataset!"
        dataset = Dataset(title)
        dataset.save()
        self.solr_orm.commit()
        self.dataset_id = dataset.id

    def test_email_request_access(self):
        with app.test_client() as client:
            app.config["ACCESS_HANDLERS"] = {"dataset": "Email"}
            # the email handler only accepts anonymous requests once the
            # catalogue-wide login requirement is lifted
            app.config["REQUIRE_LOGIN_ACCESS_REQUEST"] = False
            rv = client.post(
                url_for(
                    "request_access", entity_name="dataset", entity_id=self.dataset_id
                )
            )
            self.assertEqual(rv.status_code, 200)

    def test_email_request_access_requires_login_by_default(self):
        with app.test_client() as client:
            app.config["ACCESS_HANDLERS"] = {"dataset": "Email"}
            rv = client.get(
                url_for(
                    "request_access", entity_name="dataset", entity_id=self.dataset_id
                )
            )
            self.assertEqual(rv.status_code, 302)
            self.assertIn(url_for("login"), rv.location)

    def test_email_form_drops_recaptcha_for_logged_in_user(self):
        dataset = Dataset.query.get(self.dataset_id)
        with app.test_request_context():
            handler = EmailAccessHandler(User("test", "test@example.org", "Test User"))
            form = handler.create_form(dataset, None)
            # wtforms sets deleted fields to None instead of dropping the
            # attribute, _fields is what drives validation and rendering
            self.assertNotIn("recaptcha", form._fields)

    def test_email_form_keeps_recaptcha_for_anonymous_user(self):
        dataset = Dataset.query.get(self.dataset_id)
        with app.test_request_context():
            handler = EmailAccessHandler(AnonymousUserMixin())
            form = handler.create_form(dataset, None)
            self.assertIn("recaptcha", form._fields)

    @patch("flask_login.utils._get_user")
    def test_email_invalid_form_logged_in_user(self, current_user):
        """An empty submission must re-render the form, not fail on the
        recaptcha field the handler just deleted."""
        app.config["ACCESS_HANDLERS"] = {"dataset": "Email"}
        current_user.return_value = User("test", "test@example.org", "Test User")
        rv = app.test_client().post(
            url_for("request_access", entity_name="dataset", entity_id=self.dataset_id)
        )
        self.assertEqual(rv.status_code, 200)

    @patch("flask_login.utils._get_user")
    def test_email_valid_form_sends_the_request(self, current_user):
        """A valid submission must bind the posted data and send the email,
        the form used to be built without the request data."""
        app.config["ACCESS_HANDLERS"] = {"dataset": "Email"}
        current_user.return_value = User("test", "test@example.org", "Test User")
        with mail.record_messages() as outbox:
            rv = app.test_client().post(
                url_for(
                    "request_access", entity_name="dataset", entity_id=self.dataset_id
                ),
                data={"message": "I would like to study this dataset"},
            )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(outbox), 1)
        self.assertIn("I would like to study this dataset", outbox[0].body)

    def test_email_valid_form_sends_the_request_anonymous(self):
        app.config["ACCESS_HANDLERS"] = {"dataset": "Email"}
        app.config["REQUIRE_LOGIN_ACCESS_REQUEST"] = False
        with mail.record_messages() as outbox:
            rv = app.test_client().post(
                url_for(
                    "request_access", entity_name="dataset", entity_id=self.dataset_id
                ),
                data={
                    "name": "Someone",
                    "email": "someone@example.org",
                    "message": "Please give me access",
                },
            )
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(len(outbox), 1)
        self.assertIn("someone@example.org", outbox[0].body)

    @unittest.skip("Not included in the test")
    def test_mail(self):
        with mail.record_messages() as outbox:
            mail.send_message(
                subject="testing", body="test", recipients=["to@elixir-luxembourg.org"]
            )
            assert len(outbox) == 1
            assert outbox[0].subject == "testing"

    def tearDown(self):
        app.config["REQUIRE_LOGIN_ACCESS_REQUEST"] = True
        app.config["_solr_orm"].delete(query="*:*")
        app.config["_solr_orm"].commit()
