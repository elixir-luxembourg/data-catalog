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
"""
 datacatalog.usage_metrics
 -------------------

Usage metrics of the records: page views read from Matomo's reporting API and
access requests read from REMS. The `flask usage-metrics update` command
writes them onto the solr records, so that rendering a page never calls
Matomo or REMS.

Both sources are optional:
    - views need MATOMO_URL and MATOMO_SITE_ID (and MATOMO_TOKEN for the update)
    - access requests need the REMS access handler for datasets and REMS_URL
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import unquote

import pysolr
import requests
from solrorm import SolrQueryException

from . import app

logger = logging.getLogger(__name__)

VIEWS_TOTAL = "views_total"
VIEWS_RECENT = "views_recent"
ACCESS_REQUESTS = "access_requests"
METRIC_FIELDS = (VIEWS_TOTAL, VIEWS_RECENT, ACCESS_REQUESTS)

# number of days counted in views_recent
RECENT_VIEWS_DAYS = 90
# first day counted in views_total, unless MATOMO_START_DATE says otherwise
DEFAULT_MATOMO_START_DATE = "2015-01-01"
REMS_ACCESS_HANDLERS = ("Rems", "RemsOidc")
DRAFT_STATE_SUFFIX = "/draft"
UPDATE_BATCH_SIZE = 500

# a record page, /e/<entity name>/<entity id>, in a Matomo page url or label
RECORD_PATH = re.compile(r"(?:^|/)e/(?P<entity_name>[^/?#]+)/(?P<entity_id>[^/?#]+)")


class UsageMetricsException(Exception):
    pass


def views_enabled(config: Mapping = None) -> bool:
    """
    Whether page views are collected: Matomo is configured.
    """
    config = app.config if config is None else config
    return bool(config.get("MATOMO_URL") and config.get("MATOMO_SITE_ID"))


def access_requests_enabled(config: Mapping = None) -> bool:
    """
    Whether access requests are counted: datasets are requested through REMS.
    """
    config = app.config if config is None else config
    handler = config.get("ACCESS_HANDLERS", {}).get("dataset")
    return bool(config.get("REMS_URL")) and handler in REMS_ACCESS_HANDLERS


def usage_metrics_enabled(config: Mapping = None) -> bool:
    return views_enabled(config) or access_requests_enabled(config)


def entity_metric_fields(entity_class) -> List[str]:
    """
    The usage metric fields an entity class declares.
    """
    return [name for name in METRIC_FIELDS if name in entity_class._solr_fields]


class MatomoClient:
    """
    Reads the page views of a Matomo site with the reporting API.
    The token is sent in the body of a POST request, never in the url.
    """

    def __init__(
        self,
        url: str,
        site_id,
        token: str,
        verify_ssl: bool = True,
        timeout: int = 300,
    ) -> None:
        self.url = url.rstrip("/") + "/index.php"
        self.site_id = site_id
        self.token = token
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def record_page_views(self, date: str) -> Counter:
        """
        Page views of the record pages over a date range.
        @param date: a Matomo range, e.g. "2015-01-01,today" or "last90"
        @return: Counter of views by (entity name, entity id)
        """
        response = requests.post(
            self.url,
            data={
                "module": "API",
                "method": "Actions.getPageUrls",
                "idSite": self.site_id,
                "period": "range",
                "date": date,
                "flat": 1,
                "filter_limit": -1,
                "format": "JSON",
                "token_auth": self.token,
            },
            verify=self.verify_ssl,
            timeout=self.timeout,
        )
        response.raise_for_status()
        rows = response.json()
        if isinstance(rows, dict):
            raise UsageMetricsException(f"Matomo answered: {rows.get('message', rows)}")
        views = Counter()
        for row in rows:
            record = parse_record_path(row.get("url") or row.get("label") or "")
            if record:
                views[record] += int(row.get("nb_hits") or 0)
        return views


def parse_record_path(url: str) -> Optional[Tuple[str, str]]:
    """
    The record a page url points to.
    @param url: a page url or path, e.g. https://host/e/dataset/abc?x=1
    @return: (entity name, entity id), or None if it is not a record page
    """
    match = RECORD_PATH.search(url)
    if not match:
        return None
    return match.group("entity_name"), unquote(match.group("entity_id"))


def count_access_requests(applications: Iterable[Mapping]) -> Counter:
    """
    Number of access requests per dataset: every application but drafts,
    counted once for each dataset it asks for.
    @param applications: REMS applications as the API returns them; read as
    plain JSON, only the state and the resources' ids are needed
    @return: Counter of applications by dataset id
    """
    counts = Counter()
    for application in applications:
        if (application.get("application/state") or "").endswith(DRAFT_STATE_SUFFIX):
            continue
        dataset_ids = {
            resource.get("resource/ext-id")
            for resource in application.get("application/resources") or []
            if resource.get("resource/ext-id")
        }
        counts.update(dataset_ids)
    return counts


def fetch_views() -> Tuple[Counter, Counter]:
    """
    @return: the views of each record since MATOMO_START_DATE and over the
    last RECENT_VIEWS_DAYS days
    """
    token = app.config.get("MATOMO_TOKEN")
    if not token:
        raise UsageMetricsException("MATOMO_TOKEN is not set")
    client = MatomoClient(
        app.config["MATOMO_URL"],
        app.config["MATOMO_SITE_ID"],
        token,
        verify_ssl=app.config.get("MATOMO_VERIFY_SSL", True),
    )
    start_date = app.config.get("MATOMO_START_DATE", DEFAULT_MATOMO_START_DATE)
    views_total = client.record_page_views(f"{start_date},today")
    views_recent = client.record_page_views(f"last{RECENT_VIEWS_DAYS}")
    return views_total, views_recent


def fetch_access_requests() -> Counter:
    """
    @return: the access requests of each dataset, read with REMS_API_USER,
    which must be allowed to list every application (e.g. a reporter)
    """
    response = requests.get(
        app.config["REMS_URL"].rstrip("/") + "/api/applications",
        headers={
            "x-rems-api-key": app.config.get("REMS_API_KEY"),
            "x-rems-user-id": app.config.get("REMS_API_USER"),
        },
        verify=app.config.get("REMS_VERIFY_SSL", True),
        timeout=300,
    )
    response.raise_for_status()
    return count_access_requests(response.json())


def solr_id(entity_class, entity_id: str) -> str:
    if getattr(entity_class, "ADD_PREFIX_ID", True):
        return f"{entity_class.__name__.lower()}_{entity_id}"
    return entity_id


def write_metrics(entity_class, metrics: Mapping[str, Mapping[str, int]]) -> int:
    """
    Set usage metrics on every record of an entity type with solr atomic
    updates, leaving the other fields as they are.
    @param entity_class: the SolrEntity subclass
    @param metrics: values by entity id, for each metric field; a record
    missing from a field's values gets 0
    @return: number of records updated
    """
    fields = [name for name in metrics if name in entity_class._solr_fields]
    if not fields:
        return 0
    entity_name = entity_class.__name__.lower()
    solr_orm = app.config["_solr_orm"]
    field_updates = {f"{entity_name}_{name}": "set" for name in fields}
    entity_ids = entity_class.query.all_ids()
    for start in range(0, len(entity_ids), UPDATE_BATCH_SIZE):
        documents = [
            {
                "id": solr_id(entity_class, entity_id),
                **{
                    f"{entity_name}_{name}": int(metrics[name].get(entity_id, 0))
                    for name in fields
                },
            }
            for entity_id in entity_ids[start : start + UPDATE_BATCH_SIZE]
        ]
        solr_orm.indexer.add(documents, fieldUpdates=field_updates)
    solr_orm.commit()
    return len(entity_ids)


def update_usage_metrics(entity_names: Optional[Iterable[str]] = None) -> Dict:
    """
    Fetch the usage metrics from Matomo and REMS and store them on the records.
    @param entity_names: the entity types to update, all of them if None
    @return: number of records updated by entity name
    """
    metrics = defaultdict(dict)
    if views_enabled():
        views_total, views_recent = fetch_views()
        for field_name, views in (
            (VIEWS_TOTAL, views_total),
            (VIEWS_RECENT, views_recent),
        ):
            for entity_name in app.config["entities"]:
                metrics[entity_name][field_name] = {}
            for (entity_name, entity_id), count in views.items():
                if entity_name in metrics:
                    metrics[entity_name][field_name][entity_id] = count
    if access_requests_enabled():
        metrics["dataset"][ACCESS_REQUESTS] = fetch_access_requests()
    updated = {}
    for entity_name, entity_class in app.config["entities"].items():
        if entity_names and entity_name not in entity_names:
            continue
        if metrics.get(entity_name):
            updated[entity_name] = write_metrics(entity_class, metrics[entity_name])
    app.cache.clear()
    return updated


def stored_metrics(entity_class) -> Dict[str, Dict[str, int]]:
    """
    The usage metrics currently stored on the records of an entity type, so
    that a re-import can keep them.
    @return: metric values by attribute name, by entity id
    """
    fields = entity_metric_fields(entity_class)
    if not fields:
        return {}
    entity_name = entity_class.__name__.lower()
    solr_names = [f"{entity_name}_{name}" for name in fields]
    query = entity_class.query
    prefix_length = (
        len(entity_name) + 1 if getattr(entity_class, "ADD_PREFIX_ID", True) else 0
    )
    stored = {}
    for results in query._iter_pages(fl=",".join(["id"] + solr_names)):
        for document in results.docs:
            values = {
                name: document[solr_name]
                for name, solr_name in zip(fields, solr_names)
                if solr_name in document
            }
            if values:
                stored[document["id"][prefix_length:]] = values
    return stored


def _sum(entity_name: str, field_name: str) -> int:
    solr_orm = app.config["_solr_orm"]
    solr_field = f"{entity_name}_{field_name}"
    try:
        results = solr_orm.indexer.search(
            "*:*",
            fq=[f"type:{entity_name}"],
            rows=0,
            **{"stats": "true", "stats.field": solr_field},
        )
    except pysolr.SolrError as e:
        raise SolrQueryException(e) from e
    stats = (results.stats or {}).get("stats_fields", {}).get(solr_field) or {}
    return int(stats.get("sum") or 0)


def top_records(
    entity_class, field_name: str, rows: int = 10, extra_filters: List[str] = None
) -> List:
    """
    The records with the highest value of a metric, those at 0 left out.
    """
    entity_name = entity_class.__name__.lower()
    solr_field = f"{entity_name}_{field_name}"
    results = entity_class.query.search(
        "",
        rows=rows,
        sort=solr_field,
        sort_order="desc",
        fq=[f"type:{entity_name}", f"{solr_field}:[1 TO *]"] + (extra_filters or []),
    )
    return [
        {"entity": entity, "value": getattr(entity, field_name) or 0}
        for entity in results.entities
    ]


def statistics() -> Dict:
    """
    Totals and top records shown on the statistics page.
    """
    entities = app.config["entities"]
    result = {
        "views_enabled": views_enabled(),
        "access_requests_enabled": access_requests_enabled(),
        "views_by_type": [],
        "total_views": 0,
        "total_access_requests": 0,
        "top_viewed": [],
        "top_requested": [],
    }
    dataset_class = entities.get("dataset")
    if result["views_enabled"]:
        for entity_name, entity_class in entities.items():
            if VIEWS_TOTAL in entity_class._solr_fields:
                result["views_by_type"].append(
                    {
                        "entity_name": entity_name,
                        "value": _sum(entity_name, VIEWS_TOTAL),
                    }
                )
        result["total_views"] = sum(row["value"] for row in result["views_by_type"])
        if dataset_class and VIEWS_TOTAL in dataset_class._solr_fields:
            result["top_viewed"] = top_records(dataset_class, VIEWS_TOTAL)
    if (
        result["access_requests_enabled"]
        and dataset_class
        and ACCESS_REQUESTS in dataset_class._solr_fields
    ):
        result["total_access_requests"] = _sum("dataset", ACCESS_REQUESTS)
        result["top_requested"] = top_records(dataset_class, ACCESS_REQUESTS)
    return result
