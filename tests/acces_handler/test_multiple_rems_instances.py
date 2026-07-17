from unittest.mock import MagicMock

from flask_login import current_user

from datacatalog import app
from datacatalog.acces_handler.multiple_rems_handler import MultipleRemsAccessHandler
from datacatalog.models.dataset import Dataset
from tests.base_test import BaseTest


class TestMultipleRemsInstances(BaseTest):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            app.config["CONNECTED_INSTANCES"] = ["I1", "I2"]
            self.handler = MultipleRemsAccessHandler(
                current_user, api_username=app.config.get("REMS_API_USER")
            )

    def test_rems_connectors_created_for_all_instances(self):
        with self.app.app_context():
            keys = set(self.handler.rems_connectors.keys())
            self.assertEqual(keys, set(app.config.get("CONNECTED_INSTANCES")))

    def test_has_access_uses_instance_specific_connector(self):
        with self.app.app_context():
            ds1 = Dataset("one")
            ds1.e2e = True
            ds1.instance_id = app.config.get("CONNECTED_INSTANCES")[0]

            rc = self.handler.rems_connectors[ds1.instance_id]
            application = MagicMock()
            application.applicant.user_id = self.handler.api_username
            application.state = "application.state/approved"
            rc.applications = MagicMock(return_value=[application])

            result = self.handler.has_access(ds1)
            self.assertEqual(result.value, "approved")
