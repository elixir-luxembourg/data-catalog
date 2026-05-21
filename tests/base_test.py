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

import os
import re
import unittest

from datacatalog import app, configure_solr_orm

clean_regex = re.compile("<.*?>")


def get_clean_html_body(response):
    clean_text = re.sub(clean_regex, " ", response.data.decode("utf-8"))
    return re.sub(r"\s+", " ", clean_text)


def get_resource_path(filename):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", filename)


class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DATACATALOG_ENV"] = "test"
        app.config.from_object("datacatalog.settings.TestConfig")
        configure_solr_orm(app)
        cls.app = app

    def assert200(self, response, message=None):
        self.assertEqual(response.status_code, 200, message)
