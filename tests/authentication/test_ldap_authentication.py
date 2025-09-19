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

from unittest.mock import MagicMock, patch

from datacatalog.exceptions import AuthenticationException
from tests.base_test import BaseTest
from datacatalog import ldap
from datacatalog.authentication.ldap_authentication import (
    LDAPUserPasswordAuthentication,
)

__author__ = "Nirmeen Sallam"


class TestLDAPUserPasswordAuthentication(BaseTest):
    def setUp(self):
        super().setUp()
        self.app.config["AUTHENTICATION_METHOD"] = "LDAP"
        self.username = "testuser"
        self.password = "testpass"
        self.member_dn = f"uid={self.username},cn=users,cn=accounts,dc=uni,dc=lu"

        # Set up LDAP mocking
        self._setup_ldap_mocks()

        # Initialize LDAP authentication
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

    def test_get_user_details(self):
        self.mock_conn.search_s.return_value = self._mock_user_attributes()

        response = self.ldapauth.get_user_details(self.mock_conn, self.username)
        self.assertEqual(response, ["test@example.com", "test user"])

    def test_get_user_details_invalid_user(self):
        self.mock_conn.search_s.return_value = []

        with self.assertRaises(AuthenticationException) as cm:
            self.ldapauth.get_user_details(self.mock_conn, "invaliduser")
        self.assertEqual("Invalid user", str(cm.exception))

    def test_authenticate_user(self):
        self.mock_conn.simple_bind_s.return_value = None
        self.mock_conn.search_s.side_effect = [
            [
                (self.member_dn, {"member": [self.member_dn.encode()]})
            ],  # Group membership
            self._mock_user_attributes(),  # User details
        ]

        success, user_details = self.ldapauth.authenticate_user(
            self.username, self.password
        )
        self.assertTrue(success)
        self.assertEqual(user_details, ["test@example.com", "test user"])

    def test_authenticate_user_invalid_credentials(self):
        self.mock_conn.simple_bind_s.side_effect = self.mock_ldap.INVALID_CREDENTIALS()

        with self.assertRaises(AuthenticationException) as cm:
            self.ldapauth.authenticate_user("invaliduser", self.password)
        self.assertEqual("Invalid Credentials", str(cm.exception))

    def test_get_attributes_by_dn(self):
        # Test successful attribute retrieval
        self.mock_conn.search_s.return_value = self._mock_user_attributes()
        attributes = self.ldapauth.get_attributes_by_dn(
            self.member_dn, self.mock_conn, self.username, ["displayName", "mail"]
        )
        self.assertEqual(attributes["displayName"], "test user")
        self.assertEqual(attributes["mail"], "test@example.com")

        # Test with invalid user
        self.mock_conn.search_s.return_value = []
        attributes = self.ldapauth.get_attributes_by_dn(
            self.member_dn, self.mock_conn, "invaliduser", ["displayName", "mail"]
        )
        self.assertIsNone(attributes)

    def test_get_email_by_dn(self):
        # Test successful email retrieval
        self.mock_conn.search_s.return_value = [
            (self.member_dn, {"mail": [b"test@example.com"]})
        ]
        email = self.ldapauth.get_email_by_dn(
            self.member_dn, self.mock_conn, self.username
        )
        self.assertEqual(email, "test@example.com")

        # Test with no results
        self.mock_conn.search_s.return_value = []
        email = self.ldapauth.get_email_by_dn(
            self.member_dn, self.mock_conn, "invaliduser"
        )
        self.assertEqual(email, "")

    def test_get_displayname_by_dn(self):
        # Test successful displayname retrieval
        self.mock_conn.search_s.return_value = [
            (self.member_dn, {"displayName": [b"Test User"]})
        ]
        display_name = self.ldapauth.get_displayname_by_dn(
            self.member_dn, self.mock_conn, self.username
        )
        self.assertEqual(display_name, "Test User")

        # Test with empty displayname
        self.mock_conn.search_s.return_value = [
            (self.member_dn, {"displayName": [b""]})
        ]
        display_name = self.ldapauth.get_displayname_by_dn(
            self.member_dn, self.mock_conn, "invaliduser"
        )
        self.assertEqual(display_name, "")
