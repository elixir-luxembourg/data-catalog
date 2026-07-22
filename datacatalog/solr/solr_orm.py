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

"""
 datacatalog.solr.solr_orm
 -------------------------

Compatibility shim. The Solr ORM now lives in the standalone ``solrorm``
package; this module re-exports it so that existing
``datacatalog.solr.solr_orm`` imports keep working.
"""

from solrorm.solr_orm import *  # noqa: F401,F403
from solrorm.solr_orm import (  # noqa: F401
    SolrQuery,
    SolrAutomaticQuery,
    SolrORM,
    _SOLR_JSON_ENCODER,
)
