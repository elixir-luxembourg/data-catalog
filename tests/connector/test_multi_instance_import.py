from unittest.mock import patch, MagicMock

from datacatalog import app
from datacatalog.commands import register_cli
from datacatalog.connector.entities_connector import ImportEntitiesConnector
from datacatalog.models.dataset import Dataset
from tests.base_test import BaseTest


class FakeConnector(ImportEntitiesConnector):
    def __init__(self, instance_id, items=()):
        self.instance_id = instance_id
        self._items = list(items)

    def build_all_entities(self):
        yield from self._items


class TestMultiInstanceImport(BaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        register_cli(app)

    def setUp(self):
        super().setUp()
        solr = app.config["_solr_orm"]
        patch.object(solr, "check_schema", return_value=True).start()
        patch.object(solr, "field_type_mismatch", return_value=False).start()
        patch.object(solr, "commit").start()
        self.addCleanup(patch.stopall)
        app.config["CONNECTED_INSTANCES"] = ["I1", "I2"]

    def _invoke(self):
        return app.test_cli_runner().invoke(
            app.cli, ["import", "entities", "Daisy", "dataset"]
        )

    def test_get_importer_connectors_daisy_instances(self):
        mock_importer = MagicMock()

        with (
            patch(
                "datacatalog.connector.daisy_connector.DaisyConnector.__init__",
                lambda self, url, ec, verify_ssl=True, instance_id=None: setattr(
                    self, "instance_id", instance_id
                ),
            ),
            patch(
                "datacatalog.importer.entities_importer.EntitiesImporter", mock_importer
            ),
        ):
            result = self._invoke()

        self.assertEqual(result.exit_code, 0, result.output)
        connectors = mock_importer.call_args[0][0]
        self.assertEqual({c.instance_id for c in connectors}, {"I1", "I2"})

    def test_entities_importer_sets_instance_id_and_saves(self):
        d1, d2 = Dataset("d1"), Dataset("d2")

        with (
            patch("datacatalog.connector.daisy_connector.DaisyConnector") as MockDaisy,
            patch.object(Dataset, "save"),
        ):
            MockDaisy.side_effect = [
                FakeConnector("I1", [d1]),
                FakeConnector("I2", [d2]),
            ]
            result = self._invoke()

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(d1.instance_id, "I1")
        self.assertEqual(d2.instance_id, "I2")
