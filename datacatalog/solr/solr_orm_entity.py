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
 datacatalog.solr.solr_orm_entity
 --------------------------------

Compatibility shim. The Solr ORM now lives in the standalone ``solrorm``
package; the generic entity base class is re-exported from there.

datacatalog extends it with file-attachment helpers (backed by the WebDAV file
storage connector). These are datacatalog-specific and therefore do not belong
in the neutral ``solrorm`` library, so they are *attached to* the base class
here rather than defined in ``solrorm``.

Important: the methods are attached to ``solrorm``'s ``SolrEntity`` itself
(not to an intermediate subclass). ``solrorm``'s ORM discovers entity classes
via ``SolrEntity.__subclasses__()``, which only returns *direct* subclasses;
inserting an intermediate class would hide the concrete entity models
(Dataset, Study, Project, Compound, ...) from that discovery.
"""

from solrorm.solr_orm_entity import *  # noqa: F401,F403
from solrorm.solr_orm_entity import (  # noqa: F401
    DATETIME_FORMAT,
    DATETIME_FORMAT_NO_MICRO,
    SolrEntity,
)

from .. import app
from ..connector.file_storage_connectors.webdav_file_connector import (
    WebdavFileStorageConnector,
)


def _attachment_url(self) -> str | None:
    storage_root = app.config.get("PUBLIC_FILE_STORAGE_ROOT")
    if not storage_root:
        return None
    entity_name = self.__class__.__name__.lower()
    return f"{storage_root}/{entity_name}/{self.id}"


def _attachment_exists(self) -> bool:
    """
    This method checks if the entity has attachment files stored in the file storage

    Returns:
        bool: True if attachments were found, else False
    """
    attachments_folder = self.attachment_url()
    if attachments_folder is None:
        return False
    connector = WebdavFileStorageConnector()
    return connector.folder_exists(attachments_folder)


def _list_attached_files(self) -> list:
    """
    This method search for the files attached to this entity in the file storage.

    Returns:
        list: A list built by parse_webdav_response if the requests was answered successfully. [] if not
    """
    attachments_folder = self.attachment_url()
    if attachments_folder is None:
        return []
    connector = WebdavFileStorageConnector()
    return connector.list_files(attachments_folder)


# Attach the datacatalog-specific attachment helpers to the shared base class
# so that concrete models subclass ``solrorm.SolrEntity`` *directly* (keeping
# ``__subclasses__()`` discovery intact) while still gaining these methods.
SolrEntity.attachment_url = _attachment_url
SolrEntity.attachment_exists = _attachment_exists
SolrEntity.list_attached_files = _list_attached_files
