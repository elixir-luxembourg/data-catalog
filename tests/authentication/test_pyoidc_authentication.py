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

    @patch("datacatalog.authentication.pyoidc_authentication.session")
    @patch("datacatalog.authentication.pyoidc_authentication.redirect")
    def test_authenticate_user_redirect(self, mock_redirect, mock_session):
        session_data = {}
        mock_session.__setitem__ = lambda self, k, v: session_data.update({k: v})
        mock_session.__getitem__ = lambda self, k: session_data[k]
        mock_redirect.return_value.status_code = 303

        mock_auth_req = MagicMock()
        self.pyauth.oidc_client.construct_AuthorizationRequest.return_value = (
            mock_auth_req
        )

        with patch.object(
            self.pyauth, "get_redirect_uri", return_value=f"{BASE_URL}/pyoidc/authz"
        ):
            response = self.pyauth.authenticate_user()

        self.assertIn("state", session_data)
        self.assertIn("nonce", session_data)

        args = self.pyauth.oidc_client.construct_AuthorizationRequest.call_args[1][
            "request_args"
        ]
        self.assertEqual(args["client_id"], PYOIDC_CLIENT_ID)
        self.assertEqual(args["response_type"], "code")
        self.assertEqual(args["scope"], ["openid"])
        self.assertEqual(args["state"], session_data["state"])
        self.assertEqual(args["nonce"], session_data["nonce"])
        self.assertEqual(response.status_code, 303)

    def test_get_logout_url_unauthenticated_user(self):
        self.pyauth.oidc_client.end_session_endpoint = f"{PYOIDC_IDP_URL}/logout"
        self.pyauth.oidc_client.registration_response = {
            "post_logout_redirect_uris": [f"{BASE_URL}/pyoidc/logged_out"]
        }

        mock_user = MagicMock()
        mock_user.is_authenticated = False

        logout_url = self.pyauth.get_logout_url(mock_user)

        self.assertTrue(logout_url.startswith(f"{PYOIDC_IDP_URL}/logout?"))
        self.assertNotIn("id_token_hint=", logout_url)

    def test_get_logout_url_authenticated_user(self):
        self.pyauth.oidc_client.end_session_endpoint = f"{PYOIDC_IDP_URL}/logout"
        self.pyauth.oidc_client.registration_response = {
            "post_logout_redirect_uris": [f"{BASE_URL}/pyoidc/logged_out"]
        }

        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.extra = {"id_token": "test_token_123"}

        logout_url = self.pyauth.get_logout_url(mock_user)

        self.assertTrue(logout_url.startswith(f"{PYOIDC_IDP_URL}/logout?"))
        self.assertIn("id_token_hint=test_token_123", logout_url)
