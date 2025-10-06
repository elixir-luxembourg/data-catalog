import pytest
from pytest_factoryboy import register

from datacatalog.connector.rems_client import RemsClient, Application
from tests.factories import (
    CatalogueItemFactory,
    FormFactory,
    CreateApplicationCommandFactory,
    SaveDraftCommandFactory,
    AcceptLicensesCommandFactory,
    ResourceFactory,
    CreateResourceCommandFactory,
    UserWithAttributesFactory,
    CreateApplicationResponseFactory,
    SuccessResponseFactory,
    CreateResponseFactory,
)


register(CatalogueItemFactory)
register(FormFactory)
register(CreateApplicationCommandFactory)
register(CreateApplicationResponseFactory)
register(SaveDraftCommandFactory)
register(SuccessResponseFactory)
register(AcceptLicensesCommandFactory)
register(ResourceFactory)
register(CreateResourceCommandFactory)
register(UserWithAttributesFactory)
register(CreateResponseFactory)


@pytest.fixture
def rems_client():
    return RemsClient(
        base_url="https://mock-rems.com",
        api_key="test-api-key",
        api_username="test-user",
        admin_user="test-admin",
    )


@pytest.fixture
def rems_application():
    return Application(
        **{
            "application/workflow": {
                "workflow/id": 0,
                "workflow/type": "string",
                "workflow.dynamic/handlers": [
                    {
                        "userid": "string",
                        "name": "string",
                        "email": "string",
                        "organizations": [{"organization/id": "string"}],
                        "notification-email": "string",
                        "researcher-status-by": "string",
                        "handler/active?": True,
                        "additionalProp1": "string",
                        "additionalProp2": "string",
                        "additionalProp3": "string",
                    }
                ],
                "workflow/voting": {"type": "handlers-vote"},
                "workflow/anonymize-handling": True,
                "workflow/processing-states": [
                    {
                        "processing-state/value": "string",
                        "processing-state/title": {
                            "fi": "text in Finnish",
                            "en": "text in English",
                        },
                    }
                ],
            },
            "application/external-id": "string",
            "application/first-submitted": "2025-02-11T12:10:24.302Z",
            "application/blacklist": [
                {
                    "blacklist/user": {
                        "userid": "string",
                        "name": "string",
                        "email": "string",
                        "organizations": [{"organization/id": "string"}],
                        "notification-email": "string",
                        "researcher-status-by": "string",
                        "additionalProp1": "string",
                        "additionalProp2": "string",
                        "additionalProp3": "string",
                    },
                    "blacklist/resource": {"resource/ext-id": "string"},
                }
            ],
            "application/id": 0,
            "application/duo": {
                "duo/codes": [
                    {
                        "id": "string",
                        "restrictions": [{"type": "string", "values": ["string"]}],
                        "more-info": {
                            "fi": "text in Finnish",
                            "en": "text in English",
                        },
                        "shorthand": "string",
                        "label": {"fi": "text in Finnish", "en": "text in English"},
                        "description": {
                            "fi": "text in Finnish",
                            "en": "text in English",
                        },
                    }
                ],
                "duo/matches": [
                    {
                        "duo/id": "string",
                        "duo/shorthand": "string",
                        "duo/label": {
                            "additionalProp1": "string",
                            "additionalProp2": "string",
                            "additionalProp3": "string",
                        },
                        "resource/id": 0,
                        "duo/validation": {
                            "validity": "string",
                            "errors": [
                                {
                                    "type": "string",
                                    "additionalProp1": "string",
                                    "additionalProp2": "string",
                                    "additionalProp3": "string",
                                }
                            ],
                        },
                    }
                ],
            },
            "application/assigned-external-id": "string",
            "application/applicant": {
                "userid": "string",
                "name": "string",
                "email": "string",
                "organizations": [{"organization/id": "string"}],
                "notification-email": "string",
                "researcher-status-by": "string",
                "additionalProp1": "string",
                "additionalProp2": "string",
                "additionalProp3": "string",
            },
            "application/copied-from": {
                "application/id": 0,
                "application/external-id": "string",
            },
            "application/todo": "no-pending-requests",
            "application/members": [
                {
                    "userid": "string",
                    "name": "string",
                    "email": "string",
                    "organizations": [{"organization/id": "string"}],
                    "notification-email": "string",
                    "researcher-status-by": "string",
                    "additionalProp1": "string",
                    "additionalProp2": "string",
                    "additionalProp3": "string",
                }
            ],
            "entitlement/end": "2025-02-11T12:10:24.302Z",
            "application/resources": [
                {
                    "catalogue-item/end": "2025-02-11T12:10:24.302Z",
                    "catalogue-item/expired": True,
                    "catalogue-item/enabled": True,
                    "resource/id": 0,
                    "catalogue-item/title": {
                        "fi": "text in Finnish",
                        "en": "text in English",
                    },
                    "resource/duo": {
                        "duo/codes": [
                            {
                                "id": "string",
                                "restrictions": [
                                    {"type": "string", "values": ["string"]}
                                ],
                                "more-info": {
                                    "fi": "text in Finnish",
                                    "en": "text in English",
                                },
                                "shorthand": "string",
                                "label": {
                                    "fi": "text in Finnish",
                                    "en": "text in English",
                                },
                                "description": {
                                    "fi": "text in Finnish",
                                    "en": "text in English",
                                },
                            }
                        ]
                    },
                    "catalogue-item/infourl": {
                        "fi": "text in Finnish",
                        "en": "text in English",
                    },
                    "resource/ext-id": "string",
                    "catalogue-item/start": "2025-02-11T12:10:24.302Z",
                    "catalogue-item/archived": True,
                    "catalogue-item/id": 0,
                }
            ],
            "application/deadline": "2025-02-11T12:10:24.302Z",
            "application/accepted-licenses": {
                "additionalProp1": [0],
                "additionalProp2": [0],
                "additionalProp3": [0],
            },
            "application/invited-members": [{"name": "string", "email": "string"}],
            "application/description": "string",
            "application/votes": {
                "additionalProp1": "string",
                "additionalProp2": "string",
                "additionalProp3": "string",
            },
            "application/generated-external-id": "string",
            "application/permissions": ["application.command/copy-as-new"],
            "application/last-activity": "2025-02-11T12:10:24.302Z",
            "application/processing-state": {
                "public": {
                    "processing-state/value": "string",
                    "processing-state/title": {
                        "fi": "text in Finnish",
                        "en": "text in English",
                    },
                },
                "private": {
                    "processing-state/value": "string",
                    "processing-state/title": {
                        "fi": "text in Finnish",
                        "en": "text in English",
                    },
                },
            },
            "application/roles": ["string"],
            "application/attachments": [
                {
                    "attachment/id": 0,
                    "attachment/filename": "string",
                    "attachment/type": "string",
                    "attachment/event": {"event/id": 0},
                    "attachment/user": {
                        "userid": "string",
                        "name": "string",
                        "email": "string",
                        "organizations": [{"organization/id": "string"}],
                        "notification-email": "string",
                        "researcher-status-by": "string",
                        "additionalProp1": "string",
                        "additionalProp2": "string",
                        "additionalProp3": "string",
                    },
                    "attachment/redacted": True,
                    "attachment/can-redact": True,
                }
            ],
            "application/created": "2025-02-11T12:10:24.302Z",
            "application/state": "string",
            "application/copied-to": [
                {"application/id": 0, "application/external-id": "string"}
            ],
            "application/modified": "2025-02-11T12:10:24.302Z",
        }
    )
