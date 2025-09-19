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

from flask import session, current_app, url_for
from unittest.mock import MagicMock, patch

from datacatalog import ldap
from datacatalog.authentication.ldap_authentication import (
    LDAPUserPasswordAuthentication,
)
from datacatalog.controllers.login_controllers import load_user, save_user, login
from datacatalog.exceptions import AuthenticationException
from tests.base_test import BaseTest

__author__ = "Nirmeen Sallam"


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class TestLoginControllers(BaseTest):
    def setUp(self):
        super().setUp()
        self.app.config["AUTHENTICATION_METHOD"] = "LDAP"
        self.username = "testuser"
        self.password = "testpass"
        self.member_dn = f"uid={self.username},cn=users,cn=accounts,dc=uni,dc=lu"

        # Set up LDAP mocking
        self._setup_ldap_mocks()

        # Initialize LDAP authentication with mocked components
        self.ldapauth = LDAPUserPasswordAuthentication("ldaps://mock-ldap-host")

    def _setup_ldap_mocks(self):
        """Set up comprehensive LDAP mocking"""
        self.mock_conn = MagicMock()
        self.mock_ldap_patcher = patch(
            "datacatalog.authentication.ldap_authentication.ldap"
        )
        self.mock_ldap = self.mock_ldap_patcher.start()

        # Configure LDAP constants and exceptions
        for attr in [
            "SCOPE_SUBTREE",
            "SCOPE_BASE",
            "VERSION3",
            "OPT_X_TLS_REQUIRE_CERT",
            "OPT_X_TLS_NEVER",
            "OPT_X_TLS_NEWCTX",
        ]:
            setattr(self.mock_ldap, attr, getattr(ldap, attr))

        self.mock_ldap.SERVER_DOWN = type("SERVER_DOWN", (Exception,), {})
        self.mock_ldap.INVALID_CREDENTIALS = type(
            "INVALID_CREDENTIALS", (Exception,), {}
        )
        self.mock_ldap.initialize.return_value = self.mock_conn

        # Mock successful authentication by default
        self.mock_conn.search_s.return_value = [
            (self.member_dn, {"member": [self.member_dn.encode()]})
        ]

    def _mock_user_attributes(self, email="test@example.com", display_name="Test User"):
        """Helper to mock user attribute search results"""
        return [
            (
                self.member_dn,
                {"mail": [email.encode()], "displayName": [display_name.encode()]},
            )
        ]

    def tearDown(self):
        self.mock_ldap_patcher.stop()
        super().tearDown()

    def test_login_LDAP_invalid_form(self):
        current_app.config["authentication"] = self.ldapauth
        with self.client:
            response = self.client.post(
                url_for("login"),
                data={"username": self.username, "password": ""},
            )
            self.assertIn('id="login-form"', response.data.decode("utf-8"))

    def test_login_invalid_auth_object(self):
        authdict = dotdict({"LOGIN_TYPE": 1})
        current_app.config["authentication"] = authdict
        with self.assertRaises(AuthenticationException) as cm:
            login()
        self.assertEqual("unknown authentication type", str(cm.exception))

    def test_login_LDAP_error(self):
        current_app.config["authentication"] = self.ldapauth
        # Mock invalid credentials exception
        self.mock_conn.simple_bind_s.side_effect = self.mock_ldap.INVALID_CREDENTIALS()

        with self.client:
            response = self.client.post(
                url_for("login"),
                data={"username": "test_error", "password": "test_error"},
            )
            self.assertIn("Invalid Credentials", response.data.decode())

    def test_login_LDAP_success(self):
        current_app.config["authentication"] = self.ldapauth
        # Mock successful bind and user details
        self.mock_conn.simple_bind_s.return_value = None
        self.mock_conn.search_s.side_effect = [
            [
                (self.member_dn, {"member": [self.member_dn.encode()]})
            ],  # Group membership
            self._mock_user_attributes(),  # User details
        ]

        with self.client:
            response = self.client.post(
                url_for("login"),
                data={
                    "username": self.username,
                    "password": self.password,
                },
            )
            self.assertEqual(response.status_code, 302)

    def test_load_user(self):
        current_app.config["authentication"] = self.ldapauth
        session["_user_id"] = self.username
        session["user_details"] = {
            "email": "test",
            "display_name": self.username,
        }
        user = load_user(self.username)
        self.assertEqual(user.displayname, self.username)
        self.assertIsNone(load_user("test_none"))

    def test_save_user(self):
        session.clear()
        save_user(self.username, "test", self.username)
        self.assertEqual(session["user_details"].get("display_name"), self.username)

    def test_logout(self):
        current_app.config["authentication"] = self.ldapauth
        # Mock successful bind and user details for login
        self.mock_conn.simple_bind_s.return_value = None
        self.mock_conn.search_s.side_effect = [
            [
                (self.member_dn, {"member": [self.member_dn.encode()]})
            ],  # Group membership
            self._mock_user_attributes(),  # User details
        ]

        with self.client:
            self.client.post(
                url_for("login"),
                data={
                    "username": self.username,
                    "password": self.password,
                },
            )
            logout_response = self.client.get(url_for("logout"))
            self.assertEqual(logout_response.status_code, 302)
