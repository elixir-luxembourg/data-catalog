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


BASE_URL = app.config.get("BASE_URL", "http://localhost:5000")
PYOIDC_CLIENT_ID = app.config.get("PYOIDC_CLIENT_ID", "test-client")
PYOIDC_CLIENT_SECRET = app.config.get("PYOIDC_CLIENT_SECRET", "test-secret")
PYOIDC_IDP_URL = app.config.get("PYOIDC_IDP_URL", "https://test-idp.example.com")


class TestPyOIDCAuthentication(BaseTest):
    def setUp(self):
        super().setUp()
        self.pyauth = self._create_mocked_pyoidc_auth()

    def _create_mocked_pyoidc_auth(self):
        """Create a PyOIDC authentication instance with all network calls mocked"""
        with (
            patch(
                "datacatalog.authentication.pyoidc_authentication.Client"
            ) as mock_client_class,
            patch("datacatalog.authentication.pyoidc_authentication.app") as mock_app,
            patch("datacatalog.authentication.pyoidc_views") as mock_views_module,
        ):
            mock_oidc_client = MagicMock()
            mock_client_class.return_value = mock_oidc_client
            mock_provider_config = {
                "issuer": "https://test-idp.example.com",
                "authorization_endpoint": "https://test-idp.example.com/auth",
                "token_endpoint": "https://test-idp.example.com/token",
                "userinfo_endpoint": "https://test-idp.example.com/userinfo",
                "end_session_endpoint": "https://test-idp.example.com/logout",
            }
            mock_oidc_client.provider_config.return_value = mock_provider_config
            mock_oidc_client.store_registration_info = MagicMock()
            mock_oidc_client.client_id = PYOIDC_CLIENT_ID
            mock_oidc_client.post_logout_redirect_uris = []
            mock_oidc_client.redirect_uris = []

            mock_app.blueprints = {}
            mock_app.register_blueprint = MagicMock()
            mock_blueprint = MagicMock()
            mock_blueprint.name = "pyoidc_views"
            mock_views_module.pyoidc_views = mock_blueprint

            return PyOIDCAuthentication(
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
