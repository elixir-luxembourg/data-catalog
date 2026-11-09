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
 datacatalog.models
 -------------------

Package containing SolrEntity subclasses and corresponding SolrQuery subclasses


"""

import logging

from .. import app
from ..usage_metrics import (
    ACCESS_REQUESTS,
    VIEWS_TOTAL,
    access_requests_enabled,
    views_enabled,
)
from solrorm import SolrAutomaticQuery, SolrField, SolrIntField, SolrQuery

# installs the attachment helpers on solrorm's SolrEntity for every model
from . import entity_attachments  # noqa: F401

logger = logging.getLogger(__name__)


class DatasetQuery(SolrQuery):
    """
    SolrQuery child class for the Dataset entity
    """

    # The sort options that will be offered on the search page
    SORT_OPTIONS = ["dataset_created", "title"]
    # labels of the sort options that will be offered on the search page
    SORT_LABELS = ["dataset_created", "title"]
    # allows giving more weight to some fields than others for default search
    BOOST = app.config.get("SOLR_BOOST", "dataset_title^5 dataset_text_^1")
    # default sort option
    DEFAULT_SORT = app.config.get("SOLR_DEFAULT_SORT", "dataset_created")


class EntityWithSlugs:
    slugs = SolrField("slugs", multivalued=True)


class EntityWithUsageMetrics:
    """
    Page views of the record, written by `flask usage-metrics update`
    """

    views_total = SolrIntField("views_total")
    # views over the last usage_metrics.RECENT_VIEWS_DAYS days
    views_recent = SolrIntField("views_recent")


# (metric field, sort label) offered on the search pages when that metric is
# collected and the entity declares it
USAGE_SORT_OPTIONS = [
    ("views_total", "Most Viewed"),
    ("access_requests", "Most Requested"),
]


class UsageMetricsQuery(SolrAutomaticQuery):
    """
    SolrAutomaticQuery offering the usage metrics as extra sort options
    """

    # labels of solrorm's default sort options (title, id), in Title Case like
    # the usage metric labels
    SORT_LABELS = ["Title", "ID"]

    def usage_sort_fields(self) -> list:
        enabled = {
            VIEWS_TOTAL: views_enabled(),
            ACCESS_REQUESTS: access_requests_enabled(),
        }
        return [
            (field_name, label)
            for field_name, label in USAGE_SORT_OPTIONS
            if enabled[field_name] and field_name in self.class_object._solr_fields
        ]

    def get_sort_options(self):
        options, labels = super().get_sort_options()
        options = list(options)
        # a missing label shows the option itself, so pad before appending
        labels = list(labels) + options[len(labels) :]
        for field_name, label in self.usage_sort_fields():
            options.append(f"{self.entity_name}_{field_name}")
            labels.append(label)
        return options, labels

    def descending_sort_options(self) -> list:
        """
        The sort options that only make sense in descending order
        """
        return [
            f"{self.entity_name}_{field_name}"
            for field_name, _label in self.usage_sort_fields()
        ]
