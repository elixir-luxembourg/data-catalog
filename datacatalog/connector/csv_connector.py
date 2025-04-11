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
    datacatalog.connector.csv_connector
    -------------------

   Module containing the CSVConnector class


"""
import csv
import logging
from typing import Type, Generator

from .entities_connector import ImportEntitiesConnector
from ..solr.solr_orm_entity import SolrEntity

__author__ = "Valentin Grouès"

logger = logging.getLogger(__name__)


class CSVConnector(ImportEntitiesConnector):
    """
    Import entities directly from a CSV file
    """

    def __init__(self, csv_file_path: str, entity_class: Type[SolrEntity]) -> None:
        """
        Initialize a JSONConnector instance configuring the json file path and the entity class
        The build_all_entities methods will then create instances of entity_class from the json file json_file_path
        @param json_file_path: the path of json file containing the serialized entities
        @param entity_class: the class to instantiate
        """
        logger.info(
            "Initializing CSVConnector for %s and csv %s",
            entity_class.__name__,
            csv_file_path,
        )
        self.entity_class = entity_class
        self.csv_file_path = csv_file_path

    def build_all_entities(self) -> Generator[SolrEntity, None, None]:
        """
        Yields instances of self.entity_class parsed from the csv file self.csv_file_path
        """
        with open(self.csv_file_path, encoding="utf8") as csv_file:
            csv_reader = csv.reader(csv_file)
            next(csv_reader)
            # fields = self.entity_class()._solr_fields
            for line in csv_reader:
                new_entity = self.entity_class()
                for index, column_value in enumerate(line):
                    (
                        attribute_name,
                        transformation,
                    ) = self.entity_class().ORDER_FIELDS_CSV[index]
                    if transformation:
                        column_value = transformation(column_value)
                    setattr(new_entity, attribute_name, column_value)
                yield new_entity
