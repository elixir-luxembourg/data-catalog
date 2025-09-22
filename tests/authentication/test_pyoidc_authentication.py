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
import urllib

from flask_login import current_user

from datacatalog.authentication.pyoidc_authentication import PyOIDCAuthentication
from datacatalog import app
from tests.base_test import BaseTest


__author__ = "Nirmeen Sallam"


BASE_URL = app.config.get("BASE_URL", "http://test-oidc-url:5000")
PYOIDC_CLIENT_ID = app.config.get("PYOIDC_CLIENT_ID", "test-client")
PYOIDC_CLIENT_SECRET = app.config.get("PYOIDC_CLIENT_SECRET", "test-secret")
PYOIDC_IDP_URL = app.config.get("PYOIDC_IDP_URL", "https://test-idp.example.com")


class TestPyOIDCAuthentication(BaseTest):
    def setUp(self):
        super().setUp()
        self.pyauth = PyOIDCAuthentication(
            BASE_URL, PYOIDC_CLIENT_ID, PYOIDC_CLIENT_SECRET, PYOIDC_IDP_URL
        )

    @patch.object(PyOIDCAuthentication, "authenticate_user")
    def test_authenticate_user_redirect(self, mock_auth):
        mock_response = MagicMock()
        mock_response.status_code = 303
        mock_response.location = f"{PYOIDC_IDP_URL}/auth?client_id={PYOIDC_CLIENT_ID}"
        mock_auth.return_value = mock_response

        response = self.pyauth.authenticate_user()
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.location.startswith(PYOIDC_IDP_URL))

    @patch.object(PyOIDCAuthentication, "get_logout_url")
    def test_get_logout_url_redirect(self, mock_logout):
        mock_logout.return_value = f"{PYOIDC_IDP_URL}/logout?redirect_uri={BASE_URL}"

        logout_url = urllib.parse.unquote(self.pyauth.get_logout_url(current_user))
        self.assertTrue(logout_url.startswith(PYOIDC_IDP_URL))
        self.assertIn("redirect_uri=" + BASE_URL, logout_url)
