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

from unittest.mock import patch
from urllib.parse import parse_qs

import requests_mock

from datacatalog import app, usage_metrics
from datacatalog.commands import register_cli
from datacatalog.connector.json_connector import JSONConnector
from datacatalog.importer.entities_importer import EntitiesImporter
from datacatalog.models.dataset import Dataset
from datacatalog.usage_metrics import (
    MatomoClient,
    UsageMetricsException,
    count_access_requests,
    parse_record_path,
)
from tests.base_test import BaseTest, get_clean_html_body, get_resource_path

MATOMO_URL = "https://matomo.example.org/"
MATOMO_API = "https://matomo.example.org/index.php"
REMS_URL = "http://rems-mock-host"

VIEWS_CONFIG = {
    "MATOMO_URL": MATOMO_URL,
    "MATOMO_SITE_ID": "5",
    "MATOMO_TOKEN": "secret-token",
}
ACCESS_REQUESTS_CONFIG = {
    "REMS_URL": REMS_URL,
    "REMS_API_KEY": "key",
    "REMS_API_USER": "reporter",
    "ACCESS_HANDLERS": {"dataset": "RemsOidc"},
}
DISABLED_CONFIG = {
    "MATOMO_URL": "",
    "MATOMO_SITE_ID": "",
    "ACCESS_HANDLERS": {"dataset": "Email"},
}


def rems_application(state, *dataset_ids):
    return {
        "application/id": 1,
        "application/state": f"application.state/{state}",
        "application/resources": [
            {
                "resource/ext-id": dataset_id,
                "catalogue-item/end": None,
                "catalogue-item/title": {"en": dataset_id},
                "catalogue-item/infourl": {},
            }
            for dataset_id in dataset_ids
        ],
    }


class TestParsing(BaseTest):
    def test_parse_record_path(self):
        self.assertEqual(
            ("dataset", "abc-1"),
            parse_record_path("https://host/e/dataset/abc-1?show_deprecated=true"),
        )
        self.assertEqual(("project", "a b"), parse_record_path("e/project/a%20b"))
        self.assertEqual(
            ("study", "x"), parse_record_path("https://host/prefix/e/study/x")
        )
        self.assertIsNone(parse_record_path("https://host/datasets?query=e"))
        self.assertIsNone(parse_record_path("https://host/e/dataset"))

    def test_count_access_requests_skips_drafts_and_counts_each_dataset_once(self):
        applications = [
            rems_application("submitted", "d1"),
            rems_application("approved", "d1", "d2"),
            rems_application("rejected", "d2", "d2"),
            rems_application("draft", "d1"),
        ]
        self.assertEqual({"d1": 2, "d2": 2}, count_access_requests(applications))

    def test_matomo_page_views_sends_the_token_in_the_body(self):
        rows = [
            {
                "label": "/e/dataset/d1",
                "url": "https://host/e/dataset/d1",
                "nb_hits": 4,
            },
            {
                "label": "/e/dataset/d1?x",
                "url": "https://host/e/dataset/d1?x=1",
                "nb_hits": 1,
            },
            {"label": "e/project/p1", "nb_hits": "3"},
            {"label": "/datasets", "url": "https://host/datasets", "nb_hits": 50},
        ]
        with requests_mock.Mocker() as m:
            m.post(MATOMO_API, json=rows)
            views = MatomoClient(MATOMO_URL, 5, "secret-token").record_page_views(
                "last90"
            )
            request = m.request_history[0]
        self.assertEqual({("dataset", "d1"): 5, ("project", "p1"): 3}, views)
        self.assertNotIn("secret-token", request.url)
        body = parse_qs(request.text)
        self.assertEqual(["secret-token"], body["token_auth"])
        self.assertEqual(["Actions.getPageUrls"], body["method"])
        self.assertEqual(["last90"], body["date"])

    def test_matomo_error_raises(self):
        with requests_mock.Mocker() as m:
            m.post(MATOMO_API, json={"result": "error", "message": "no access"})
            with self.assertRaisesRegex(UsageMetricsException, "no access"):
                MatomoClient(MATOMO_URL, 5, "token").record_page_views("last90")

    def test_enabled_flags(self):
        self.assertTrue(usage_metrics.views_enabled(VIEWS_CONFIG))
        self.assertFalse(usage_metrics.views_enabled({"MATOMO_URL": MATOMO_URL}))
        self.assertTrue(usage_metrics.access_requests_enabled(ACCESS_REQUESTS_CONFIG))
        self.assertFalse(
            usage_metrics.access_requests_enabled(
                {**ACCESS_REQUESTS_CONFIG, "ACCESS_HANDLERS": {"dataset": "Email"}}
            )
        )
        self.assertFalse(usage_metrics.usage_metrics_enabled(DISABLED_CONFIG))


class TestUsageMetricsSolr(BaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.solr_orm = app.config["_solr_orm"]
        cls.solr_orm.delete_fields()
        cls.solr_orm.create_fields()
        cls.importer = EntitiesImporter(
            [JSONConnector(get_resource_path("records.json"), Dataset)]
        )

    def setUp(self):
        self.solr_orm.delete(query="*:*")
        self.importer.import_all()
        self.datasets = sorted(Dataset.query.all(), key=lambda d: d.id)
        self.first, self.second = self.datasets[0], self.datasets[1]
        self.client = app.test_client()

    def enabled(self, *configs):
        values = {}
        for config in configs:
            values.update(config)
        return patch.dict(app.config, values)

    def update_with_sources(self, views_total, views_recent, applications):
        """
        Run update_usage_metrics with Matomo and REMS answering the given data
        """
        with requests_mock.Mocker(real_http=True) as m:
            m.post(
                MATOMO_API,
                [
                    {
                        "json": [
                            {"url": f"https://h/e/{k[0]}/{k[1]}", "nb_hits": v}
                            for k, v in views.items()
                        ]
                    }
                    for views in (views_total, views_recent)
                ],
            )
            m.get(f"{REMS_URL}/api/applications", json=applications)
            return usage_metrics.update_usage_metrics()

    def write_demo_metrics(self):
        usage_metrics.write_metrics(
            Dataset,
            {
                "views_total": {self.first.id: 10, self.second.id: 30},
                "views_recent": {self.first.id: 7, self.second.id: 2},
                "access_requests": {self.first.id: 4},
            },
        )

    def test_write_metrics_keeps_the_other_fields(self):
        self.write_demo_metrics()
        first = Dataset.query.get(self.first.id)
        third = Dataset.query.get(self.datasets[2].id)
        self.assertEqual(10, first.views_total)
        self.assertEqual(7, first.views_recent)
        self.assertEqual(4, first.access_requests)
        self.assertEqual(self.first.title, first.title)
        self.assertEqual(self.first.dataset_created, first.dataset_created)
        self.assertEqual(0, third.views_total)
        self.assertEqual(len(self.datasets), Dataset.query.count())

    def test_reimport_keeps_the_metrics(self):
        self.write_demo_metrics()
        self.importer.import_all()
        first = Dataset.query.get(self.first.id)
        self.assertEqual(10, first.views_total)
        self.assertEqual(4, first.access_requests)

    def test_update_usage_metrics_from_matomo_and_rems(self):
        applications = [
            rems_application("submitted", self.first.id),
            rems_application("draft", self.second.id),
        ]
        with self.enabled(VIEWS_CONFIG, ACCESS_REQUESTS_CONFIG):
            updated = self.update_with_sources(
                {("dataset", self.first.id): 12, ("dataset", "unknown"): 3},
                {("dataset", self.first.id): 2},
                applications,
            )
        self.assertEqual(len(self.datasets), updated["dataset"])
        first = Dataset.query.get(self.first.id)
        second = Dataset.query.get(self.second.id)
        self.assertEqual(
            (12, 2, 1), (first.views_total, first.views_recent, first.access_requests)
        )
        self.assertEqual(
            (0, 0, 0), (second.views_total, second.views_recent, second.access_requests)
        )
        self.assertIsNone(Dataset.query.get("unknown"))

    def test_update_without_token_fails(self):
        with self.enabled({**VIEWS_CONFIG, "MATOMO_TOKEN": ""}):
            with self.assertRaisesRegex(UsageMetricsException, "MATOMO_TOKEN"):
                usage_metrics.update_usage_metrics()

    def test_command_without_source_does_nothing(self):
        with self.enabled(DISABLED_CONFIG):
            if "usage-metrics" not in app.cli.commands:
                register_cli(app)
            result = app.test_cli_runner().invoke(args=["usage-metrics", "update"])
        self.assertEqual(0, result.exit_code, result.output)

    def test_sort_options(self):
        with self.enabled(DISABLED_CONFIG):
            options, labels = Dataset.query.get_sort_options()
            self.assertNotIn("Most Viewed", labels)
        with self.enabled(VIEWS_CONFIG, ACCESS_REQUESTS_CONFIG):
            options, labels = Dataset.query.get_sort_options()
            self.assertEqual(len(options), len(labels))
            self.assertEqual(["Title", "ID"], labels[:2])
            self.assertEqual(
                "dataset_views_total", options[labels.index("Most Viewed")]
            )
            self.assertEqual(
                "dataset_access_requests", options[labels.index("Most Requested")]
            )
            from datacatalog.models.project import Project

            project_labels = Project.query.get_sort_options()[1]
            self.assertIn("Most Viewed", project_labels)
            self.assertNotIn("Most Requested", project_labels)

    def test_search_sorted_by_views(self):
        self.write_demo_metrics()
        with self.enabled(VIEWS_CONFIG):
            response = self.client.get(
                "/datasets?sort_by=dataset_views_total&order=desc"
            )
        self.assertEqual(200, response.status_code)
        page = response.data.decode("utf-8")
        self.assertLess(page.index(self.second.title), page.index(self.first.title))
        self.assertIn('value="dataset_views_total" data-order="desc"', page)

    def test_statistics_page(self):
        self.write_demo_metrics()
        with self.enabled(DISABLED_CONFIG):
            self.assertEqual(404, self.client.get("/statistics").status_code)
        with self.enabled(VIEWS_CONFIG, ACCESS_REQUESTS_CONFIG):
            response = self.client.get("/statistics")
        self.assertEqual(200, response.status_code)
        text = get_clean_html_body(response)
        self.assertIn("Record page views 40", text)
        self.assertIn("Dataset access requests 4", text)
        self.assertIn("Most viewed datasets", text)
        self.assertIn(f"{self.second.title} 30", text)
        self.assertIn(f"{self.first.title} 10", text)
        self.assertIn(f"{self.first.title} 4 About these numbers", text)

    def test_navbar_statistics_entry(self):
        with self.enabled(DISABLED_CONFIG):
            page = self.client.get("/about").data.decode("utf-8")
            self.assertNotIn('href="/statistics"', page)
        with self.enabled(VIEWS_CONFIG):
            page = self.client.get("/about").data.decode("utf-8")
        navbar = page[page.index("<nav") : page.index("</nav>")]
        self.assertIn('href="/statistics"', navbar)

    @patch.dict(app.config, {"NO_LANDING": False})
    def test_landing_lists(self):
        self.write_demo_metrics()
        with self.enabled(DISABLED_CONFIG):
            text = get_clean_html_body(self.client.get("/"))
            self.assertNotIn("Recently added", text)
            self.assertNotIn("Statistics", text)
        with self.enabled(VIEWS_CONFIG):
            text = get_clean_html_body(self.client.get("/"))
        self.assertIn("Recently added datasets", text)
        self.assertIn("Most viewed datasets", text)
        self.assertIn(f"{self.first.title} 7 views", text)
        self.assertIn(f"{self.second.title} 2 views", text)
        self.assertIn("Statistics", text)

    @patch.dict(app.config, {"NO_LANDING": False, "LANDING_LIST_SIZE": 1})
    def test_landing_list_size_setting(self):
        self.write_demo_metrics()
        with self.enabled(VIEWS_CONFIG):
            text = get_clean_html_body(self.client.get("/"))
        self.assertIn(f"{self.first.title} 7 views", text)
        self.assertNotIn(f"{self.second.title} 2 views", text)

    @patch.dict(app.config, {"NO_LANDING": False})
    def test_landing_featured_entities_setting(self):
        self.write_demo_metrics()
        with self.enabled(VIEWS_CONFIG, {"LANDING_FEATURED_ENTITIES": ["project"]}):
            text = get_clean_html_body(self.client.get("/"))
        self.assertNotIn("Recently added", text)
        self.assertNotIn("Most viewed datasets", text)

    def test_dataset_page_shows_usage(self):
        self.write_demo_metrics()
        dataset = Dataset.query.get(self.first.id)
        dataset.e2e = True
        dataset.save(commit=True)
        url = f"/e/dataset/{self.first.id}"
        with self.enabled(DISABLED_CONFIG):
            self.assertNotIn("Views 10", get_clean_html_body(self.client.get(url)))
        with self.enabled(VIEWS_CONFIG, ACCESS_REQUESTS_CONFIG):
            text = get_clean_html_body(self.client.get(url))
        self.assertIn("Views 10", text)
        self.assertIn("Access requests 4", text)
