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
    datacatalog.authentication
    -------------------

    Package for the abstract classs UserPasswordAuthentication, RemoteAuthentication  and its implementations
    Implementations:
        - LDAPAuthentication
        - OIDCAuthentication

"""

from abc import ABCMeta, abstractmethod

__author__ = "Valentin Grouès"

from enum import Enum
from typing import Optional

from datacatalog.models.user import User


class LoginType(Enum):
    REDIRECT = 1
    FORM = 2


class Authentication(metaclass=ABCMeta):
    @abstractmethod
    def authenticate_user(self, username=None, password=None):
        """
        Check if username and password matches and if user is authorized
        @param username: name of the user
        @type username: str
        @param password: password of the user
        @type password: str
        @return an exception if not successful, a tuple containing True and the user details if successful
        """
        pass

    @abstractmethod
    def refresh_user(self, user):
        pass

    @abstractmethod
    def validate_user(self, user):
        pass


class RemoteAuthentication(Authentication, metaclass=ABCMeta):
    """
    Abstract class specifying methods to implement to authenticate users if not based on username and password
    Typically for OIDC implementation
    Is used for login process
    """

    LOGIN_TYPE = LoginType.REDIRECT

    @abstractmethod
    def get_logout_url(self, user: Optional[User] = None) -> str:
        """
        Build the logout url and returns it
        """
        pass

    @abstractmethod
    def check_and_refresh(self, user):
        pass


class UserPasswordAuthentication(metaclass=ABCMeta):
    """
    Abstract class specifying methods to implement to authenticate users
    Is used for login process
    """

    LOGIN_TYPE = LoginType.FORM

    def validate_user(self, user):
        return False

    def refresh_user(self, user):
        pass
