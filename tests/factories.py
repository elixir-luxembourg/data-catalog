from datetime import datetime

import factory
from factory import LazyFunction, List, Sequence

from datacatalog.connector.rems_client import (
    UserWithAttributes,
    Application,
    CatalogueItem,
    Form,
    CreateApplicationCommand,
    SaveDraftCommand,
    AcceptLicensesCommand,
    Resource,
    CreateResourceCommand,
    Workflow,
    V2Resource,
    ApplicationAttachment,
    OrganizationOverview,
    CreateApplicationResponse,
    SuccessResponse,
    OrganizationId,
    ResourceLicense,
    SaveDraftCommandFieldValues,
    CreateResponse,
)


class UserWithAttributesFactory(factory.Factory):
    class Meta:
        model = UserWithAttributes

    user_id = factory.Sequence(lambda n: f"user{n}")
    name = factory.Faker("name")
    email = factory.Faker("email")

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["userid"] = kwargs.pop("user_id")
        return model_class(*args, **kwargs)


class OrganizationOverviewFactory(factory.Factory):
    class Meta:
        model = OrganizationOverview

    id = factory.Faker("word")
    short_name = factory.Faker("pydict", nb_elements=5, value_types=[str])
    name = factory.Faker("pydict", nb_elements=5, value_types=[str])


class CatalogueItemFactory(factory.Factory):
    class Meta:
        model = CatalogueItem

    archived = factory.Faker("boolean")
    localizations = factory.Faker("pydict", nb_elements=5, value_types=[str])
    resource_id = factory.Sequence(lambda n: n + 1)
    start = factory.Faker("iso8601")
    resource_name = factory.Faker("word")
    organization = factory.Faker("pydict", nb_elements=5, value_types=[str])
    wfid = factory.Sequence(lambda n: n + 1)
    resid = factory.Faker("word")
    form_id = factory.Sequence(lambda n: n + 1)
    categories = factory.List(
        [factory.Faker("pydict", nb_elements=3, value_types=[str]) for _ in range(2)]
    )
    workflow_name = factory.Faker("word")
    id = factory.Sequence(lambda n: n + 1)
    expired = factory.Faker("boolean")
    end = factory.Faker("iso8601")
    enabled = factory.Faker("boolean")


class FormFactory(factory.Factory):
    class Meta:
        model = Form

    archived = factory.Faker("boolean")
    internal_name = factory.Faker("word")
    title = factory.Faker("word")
    organization = factory.SubFactory(OrganizationOverviewFactory)
    errors = factory.Faker("pydict", nb_elements=5, value_types=[str])
    id = factory.Sequence(lambda n: n + 1)
    external_title = factory.Faker("pydict", nb_elements=5, value_types=[str])
    enabled = factory.Faker("boolean")


class CreateApplicationCommandFactory(factory.Factory):
    class Meta:
        model = CreateApplicationCommand

    catalogue_item_ids = factory.List(
        [factory.Sequence(lambda n: n + 1) for _ in range(2)]
    )

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["catalogue-item-ids"] = kwargs.pop("catalogue_item_ids")
        return model_class(*args, **kwargs)


class SaveDraftCommandFieldValuesFactory(factory.Factory):
    class Meta:
        model = SaveDraftCommandFieldValues

    form = factory.Sequence(lambda n: n + 1)
    field = factory.Faker("word")
    value = factory.Faker("word")


class SaveDraftCommandFactory(factory.Factory):
    class Meta:
        model = SaveDraftCommand

    application_id = factory.Sequence(lambda n: n + 1)
    field_values = factory.List(
        [factory.SubFactory(SaveDraftCommandFieldValuesFactory) for _ in range(2)]
    )

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["application-id"] = kwargs.pop("application_id")
        kwargs["field-values"] = kwargs.pop("field_values")
        return model_class(*args, **kwargs)


class CreateApplicationResponseFactory(factory.Factory):
    class Meta:
        model = CreateApplicationResponse

    success = factory.Faker("boolean")
    application_id = factory.Sequence(lambda n: n + 1)

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["application-id"] = kwargs.pop("application_id")
        return model_class(*args, **kwargs)


class SuccessResponseFactory(factory.Factory):
    class Meta:
        model = SuccessResponse

    success = factory.Faker("boolean")
    errors = factory.List(
        [factory.Faker("pydict", nb_elements=3, value_types=[str]) for _ in range(2)]
    )


class AcceptLicensesCommandFactory(factory.Factory):
    class Meta:
        model = AcceptLicensesCommand

    application_id = factory.Sequence(lambda n: n + 1)
    accepted_licenses = factory.List(
        [factory.Sequence(lambda n: n + 1) for _ in range(2)]
    )

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["application-id"] = kwargs.pop("application_id")
        kwargs["accepted-licenses"] = kwargs.pop("accepted_licenses")
        return model_class(*args, **kwargs)


class ResourceLicenseFactory(factory.Factory):
    class Meta:
        model = ResourceLicense

    id = factory.Sequence(lambda n: n + 1)
    licensetype = factory.Faker("word")
    organization = factory.SubFactory(OrganizationOverviewFactory)
    enabled = factory.Faker("boolean")
    archived = factory.Faker("boolean")
    localizations = factory.Faker("pydict", nb_elements=5, value_types=[str])


class ResourceFactory(factory.Factory):
    class Meta:
        model = Resource

    id = factory.Sequence(lambda n: n + 1)
    organization = factory.SubFactory(OrganizationOverviewFactory)
    resid = factory.Faker("word")
    enabled = factory.Faker("boolean")
    archived = factory.Faker("boolean")
    licenses = factory.List(
        [factory.SubFactory(ResourceLicenseFactory) for _ in range(2)]
    )
    duo = factory.Faker("pydict", nb_elements=3, value_types=[str])

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["resource/duo"] = kwargs.pop("duo")
        return model_class(*args, **kwargs)


class OrganizationIdFactory(factory.Factory):
    class Meta:
        model = OrganizationId

    id = factory.Faker("word")

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["organization/id"] = kwargs.pop("id")
        return model_class(*args, **kwargs)


class CreateResourceCommandFactory(factory.Factory):
    class Meta:
        model = CreateResourceCommand

    organization = factory.SubFactory(OrganizationIdFactory)
    resid = factory.Faker("word")
    licenses = factory.List([factory.Sequence(lambda n: n + 1) for _ in range(2)])


class CreateResponseFactory(factory.Factory):
    class Meta:
        model = CreateResponse

    success = factory.Faker("boolean")
    id = factory.Sequence(lambda n: n + 1)


class WorkflowFactory(factory.Factory):
    class Meta:
        model = Workflow

    id = factory.Sequence(lambda n: n + 1)
    type = factory.Faker("word")

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["workflow/id"] = kwargs.pop("id")
        kwargs["workflow/type"] = kwargs.pop("type")
        return model_class(*args, **kwargs)


class V2ResourceFactory(factory.Factory):
    class Meta:
        model = V2Resource

    end = factory.Faker("iso8601")
    expired = factory.Faker("boolean")
    enabled = factory.Faker("boolean")
    id = factory.Sequence(lambda n: n + 1)
    title = factory.Faker("pydict", nb_elements=5, value_types=[str])
    infourl = factory.Faker("pydict", nb_elements=5, value_types=[str])
    ext_id = factory.Faker("word")
    start = factory.Faker("iso8601")
    archived = factory.Faker("boolean")
    catalog_item_id = factory.Sequence(lambda n: n + 1)

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["catalogue-item/end"] = kwargs.pop("end")
        kwargs["catalogue-item/expired"] = kwargs.pop("expired")
        kwargs["catalogue-item/enabled"] = kwargs.pop("enabled")
        kwargs["resource/id"] = kwargs.pop("id")
        kwargs["catalogue-item/title"] = kwargs.pop("title")
        kwargs["catalogue-item/infourl"] = kwargs.pop("infourl")
        kwargs["resource/ext-id"] = kwargs.pop("ext_id")
        kwargs["catalogue-item/start"] = kwargs.pop("start")
        kwargs["catalogue-item/archived"] = kwargs.pop("archived")
        kwargs["catalogue-item/id"] = kwargs.pop("catalog_item_id")
        return model_class(*args, **kwargs)


class ApplicationAttachmentFactory(factory.Factory):
    class Meta:
        model = ApplicationAttachment

    id = factory.Sequence(lambda n: n + 1)
    filename = factory.Faker("file_name")
    type = factory.Faker("mime_type")
    event = factory.Faker("pydict", nb_elements=3)

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        kwargs["attachment/id"] = kwargs.pop("id")
        kwargs["attachment/filename"] = kwargs.pop("filename")
        kwargs["attachment/type"] = kwargs.pop("type")
        kwargs["attachment/event"] = kwargs.pop("event")
        return model_class(*args, **kwargs)


class ApplicationFactory(factory.Factory):
    """
    Factory creates Application objects with empty fields.
    Use rems_application fixture instead.
    """

    class Meta:
        model = Application

    id = Sequence(lambda n: n)
    workflow = factory.SubFactory(WorkflowFactory)
    state = factory.Iterator(["draft", "submitted", "approved", "rejected"])
    applicant = factory.SubFactory(UserWithAttributesFactory)
    resources = List([factory.SubFactory(V2ResourceFactory) for _ in range(2)])
    forms = List([factory.SubFactory(FormFactory) for _ in range(2)])
    attachments = List(
        [factory.SubFactory(ApplicationAttachmentFactory) for _ in range(2)]
    )
    organization = factory.SubFactory(OrganizationOverviewFactory)
    created = LazyFunction(lambda: datetime.now().isoformat())
    modified = LazyFunction(lambda: datetime.now().isoformat())
