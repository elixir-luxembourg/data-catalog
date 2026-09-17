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
import json
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from datacatalog import app
from solrorm.orm import _SOLR_JSON_ENCODER
from tests.base_test import BaseTest

__author__ = "Nirmeen Sallam"


def test_solr_json_encoder():
    def encode(value):
        return json.loads(_SOLR_JSON_ENCODER.encode({"v": value}))["v"]

    assert (
        encode(datetime(2025, 6, 1, 12, 30, 45, 123456)) == "2025-06-01T12:30:45.123Z"
    )
    assert (
        encode(datetime(2025, 6, 2, 8, tzinfo=timezone(timedelta(hours=2))))
        == "2025-06-02T06:00:00.000Z"
    )
    assert encode(date(2025, 6, 3)) == "2025-06-03T00:00:00Z"
    with pytest.raises(TypeError, match="set is not JSON serializable"):
        encode({1})
    # Without _SOLR_JSON_ENCODER, pysolr's default fails on datetime.
    with pytest.raises(TypeError, match="datetime is not JSON serializable"):
        json.JSONEncoder().encode(datetime(2025, 6, 1))


class TestModels(BaseTest):
    def setUp(self):
        self.solr_orm = app.config["_solr_orm"]
        self.solr_orm.delete_fields()
        self.solr_orm.commit()

    def test_initialize_solr_query_fields(self):
        """Every field named in SOLR_QUERY_TEXT_FIELD is copied into _text_.

        The configuration is now the whole story: solrorm no longer derives any
        source from SOLR_QUERY_SEARCH_EXTENDED*, so a field is searchable if,
        and only if, it is listed. Asserting against the live schema is what
        catches a field that was listed but never reached solr.
        """
        self.solr_orm.create_fields()
        directives = {
            (directive["source"], directive["dest"])
            for directive in self.solr_orm.indexer_schema.copy_fields()
        }
        for entity_name in app.config["entities"]:
            # ask the ORM, not the config: this resolves the per-entity fallback
            # for an entity SOLR_QUERY_TEXT_FIELD does not mention
            for field_name in self.solr_orm.query_fields_for_entity(entity_name):
                # "id" is the one source every entity shares, so it is unprefixed
                source = "id" if field_name == "id" else f"{entity_name}_{field_name}"
                self.assertIn((source, f"{entity_name}_text_"), directives)

    def test_create_field(self):
        self.solr_orm.indexer_schema.create_field(
            "dataset_test", "string", False, False, False
        )
        self.assertIn(
            "dataset_test",
            requests.get(self.solr_orm.indexer_schema.url + "/fields").content.decode(
                "utf-8"
            ),
        )
        self.solr_orm.indexer_schema.delete_field("dataset_test")
        self.solr_orm.commit()

    def test_update_field(self):
        self.solr_orm.indexer_schema.create_field(
            "dataset_test", "string", False, False, False
        )
        self.solr_orm.indexer_schema.update_field(
            "dataset_test", "text_en", False, False, False
        )
        self.assertIn(
            "text_en",
            requests.get(
                self.solr_orm.indexer_schema.url + "/fields/dataset_test"
            ).content.decode("utf-8"),
        )
        self.solr_orm.indexer_schema.delete_field("dataset_test")
        self.solr_orm.commit()

    def test_delete_field(self):
        self.solr_orm.indexer_schema.create_field(
            "dataset_test", "string", False, False, False
        )
        self.solr_orm.indexer_schema.delete_field("dataset_test")
        class_attributes = requests.get(
            self.solr_orm.indexer_schema.url + "/fields"
        ).content.decode("utf-8")
        self.assertNotIn("dataset_test", class_attributes)
        self.solr_orm.commit()

    def tearDown(self):
        self.solr_orm.delete_fields()
        self.solr_orm.commit()
