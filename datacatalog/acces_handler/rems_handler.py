#  coding=utf-8
#  DataCatalog
#  Copyright (C) 2020  University of Luxembourg
#
#  This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import logging
import os
import tempfile
from abc import ABCMeta, abstractmethod
from datetime import datetime as dt

from flask import request
from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    SubmitField,
    BooleanField,
    SelectField,
    DateField,
    FileField,
    FieldList,
    FormField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, Length, Email, AnyOf, Optional

from .access_handler import AccessHandler, ApplicationState, Application
from .email_handler import EmailAccessHandler
from .. import app
from ..connector.rems_connector import RemsConnector, CatalogueItemDoesntExistException
from ..exceptions import CouldNotCloseApplicationException
from ..forms import MultiCheckboxField

logger = logging.getLogger(__name__)


class RemsAccessHandler(AccessHandler):
    ALLOW_USER_ACTIONS = False

    def requires_logged_in_user(self, entity):
        if entity.e2e:
            return True
        else:
            return self.fallback_handler.requires_logged_in_user(entity)

    def supports_listing_accesses(self):
        return True

    def __init__(
        self,
        user,
        api_username=None,
        api_key=None,
        host=None,
        workflow_id=None,
        verify_ssl=True,
        all_ids=None,
    ):
        logger.debug("Initializing rems access handler")
        if all_ids is None:
            all_ids = []
        self.all_ids = all_ids
        self.api_username = api_username
        self.rems_connector = RemsConnector(
            api_username=api_username,
            api_key=api_key,
            host=host,
            workflow_id=workflow_id,
            verify_ssl=verify_ssl,
            admin_user=app.config["REMS_API_USER"],
        )
        # trying to create user in case it doesn't exist
        if user.is_authenticated:
            logger.debug("User is authenticated, will create rems user")
            self.rems_connector.create_user(api_username, user.displayname, user.email)
        super().__init__(user)
        self.fallback_handler = EmailAccessHandler(user)
        self.template = "request_access_rems.html"

    def has_access(self, dataset):
        logger.info(
            "Checking if user %s has access to dataset %s",
            current_user.id if current_user.is_authenticated else "Anonymous",
            dataset.id,
        )
        if not dataset.e2e:
            logger.info("e2e flow not enabled for dataset %s, no access", dataset.id)
            return False
        applications = self.rems_connector.applications(f'resource:"{dataset.id}"')
        has_submitted = False
        if not applications:
            return False
        for application in applications:
            if application.applicant.user_id != self.api_username:
                continue
            if application.state[18:] == ApplicationState.approved.value:
                logger.info(
                    "application found for user %s, approved state", self.api_username
                )
                return ApplicationState.approved
            if application.state[18:] == ApplicationState.submitted.value:
                has_submitted = True
        if has_submitted:
            logger.info(
                "application found for user %s, submitted state", self.api_username
            )
            return ApplicationState.submitted
        return False

    def close_application(self, application_id):
        logger.info(
            "closing application %s for user %s", application_id, current_user.id
        )
        application_id = int(application_id)
        application_raw = self.rems_connector.get_application(application_id)
        application = self.build_application(application_raw)
        if application.applicant_id != current_user.id:
            raise CouldNotCloseApplicationException("not authorized")
        self.rems_connector.close_application(application_id)
        return True

    def my_applications(self):
        logger.debug("getting list of applications")
        applications = self.rems_connector.my_applications()
        results = []
        for a in applications:
            if a.state[18:] != ApplicationState.draft.value and (
                a.resources[0].ext_id in self.all_ids or not self.all_ids
            ):
                application = self.build_application(a)
                results.append(application)
        logger.debug("%d applications found", len(results))
        return results

    def apply(self, dataset, form):
        logger.info("Access request through rems to dataset %s", dataset.id)
        if not dataset.e2e or getattr(dataset, "form_id", None) is None:
            logger.info(
                "e2e or form_id not enabled for this dataset, fallback to email handler"
            )
            self.fallback_handler.apply(dataset, form)
            return

        try:
            catalogue_item = self.rems_connector.get_catalogue_item(dataset)
        except CatalogueItemDoesntExistException as e:
            logger.error(e)
            return self.fallback_handler.apply(dataset, form)

        rems_form = self.rems_connector.get_form_for_catalogue_item(
            catalogue_item.form_id
        )
        field_values = {}
        # create application
        application_id = self.rems_connector.create_application([catalogue_item.id])
        for field in rems_form.fields:
            rems_field_id = field.fieldid
            wtf_field = FieldBuilder.build_field_builder(field)
            flask_form_value = getattr(form, rems_field_id).data
            field_values[rems_field_id] = wtf_field.transform_value(
                flask_form_value, self.rems_connector, application_id
            )
        # save draftFormTemplate
        self.rems_connector.save_application_draft(
            application_id, rems_form.id, field_values
        )
        resource_id = catalogue_item.resource_id
        resource = self.rems_connector.get_resource(resource_id)
        licenses = resource.licenses
        license_ids = []
        for license in licenses:
            license_id = license.id
            license_ids.append(license_id)
        self.rems_connector.accept_license(application_id, license_ids)
        self.rems_connector.submit_application(application_id)

    def get_datasets(self):
        pass

    def create_form(self, dataset, form_data: dict | None):
        class FormClass(FlaskForm):
            pass

        logger.debug("Creating form for rems request for dataset %s", dataset.id)
        if not dataset.e2e or getattr(dataset, "form_id", None) is None:
            logger.debug("e2e not enabled for this dataset, fallback to email form")
            return self.fallback_handler.create_form(dataset, form_data)

        try:
            catalogue_item = self.rems_connector.get_catalogue_item(dataset)
        except CatalogueItemDoesntExistException as e:
            logger.error(e)
            return self.fallback_handler.create_form(dataset, form_data)
        resource_id = catalogue_item.resource_id
        resource = self.rems_connector.get_resource(resource_id)

        form = self.rems_connector.get_form_for_catalogue_item(catalogue_item.form_id)
        fields = form.fields
        for field in fields:
            try:
                wtf_field = FieldBuilder.build_field(field)
            except UnsupportedFieldType:
                logger.error(f"unsupported field type {field.fieldtype}")
                continue
            setattr(FormClass, field.fieldid, wtf_field)
        licenses = resource.licenses
        for license in licenses:
            license_id = license.id
            title = license.localizations["en"]["title"]
            url = license.localizations["en"]["textcontent"]
            label = f"I acknowledge the {title}"
            license_field = BooleanField(
                label,
                render_kw={"url": url},
                validators=[
                    DataRequired(),
                    AnyOf([True], message="You must accept the agreement"),
                ],
            )
            field_id = f"license_{license_id}"
            setattr(FormClass, field_id, license_field)
        use_conditions = dataset.use_conditions or []
        logger.debug("processing use conditions, %d conditions", len(use_conditions))
        for index, use_condition in enumerate(use_conditions):
            field_id = f"use_condition_{index}"
            values = []
            use_condition_note = use_condition.get("use_condition_note")
            use_class = use_condition.get("use_class") or ""
            use_class_label = use_condition.get("use_class_label", "")
            use_condition_rule = use_condition.get("use_condition_rule", "")
            use_class_note = use_condition.get("use_class_note", "")
            tooltip_values = []
            if use_condition_note:
                values.append(use_condition_note)
            if use_class_label:
                values.append(f"({use_class_label})")
            if use_condition_rule:
                tooltip_values.append(use_condition_rule)
            if use_class:
                tooltip_values.append(f"GA4GH use condition code: {use_class}")
            if use_class_note:
                tooltip_values.append(f"{use_class_note}")
            tooltip = ", ".join(tooltip_values)
            setattr(
                FormClass,
                field_id,
                BooleanField(
                    " ".join(values),
                    validators=[
                        DataRequired(),
                        AnyOf([True], message="You must accept all the use conditions"),
                    ],
                    render_kw={
                        "compact": True,
                        "tooltip": tooltip,
                        "use_condition_rule": use_condition["use_condition_rule"],
                    },
                ),
            )
        setattr(FormClass, "submit", SubmitField("Send"))
        return FormClass() if form_data is None else FormClass(formdata=form_data)

    @staticmethod
    def build_application(application):
        try:
            state = ApplicationState(application.state[18:])
        except ValueError as e:
            logger.error(e)
            state = None
        return Application(
            application_id=application.id,
            state=state,  # could be None if state is not recognized
            entity_id=application.resources[0].ext_id,
            entity_title=application.resources[0].title["en"],
            creation_date=dt.fromisoformat(application.created),
            applicant_id=application.applicant.user_id,
            external_id=application.external_id,
        )


def get_all_subclasses(cls):
    all_subclasses = []

    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))

    return all_subclasses


class UnsupportedFieldType(Exception):
    pass


class FieldBuilder(metaclass=ABCMeta):
    SUPPORTED_FIELD_TYPE = []

    @staticmethod
    def build_field_builder(rems_field):
        field_builders = get_all_subclasses(FieldBuilder)
        types_named = {
            field_builder.__name__: field_builder for field_builder in field_builders
        }
        for field_builder in types_named.values():
            if field_builder.can_handle(rems_field):
                fb = field_builder(rems_field)
                return fb
        raise UnsupportedFieldType(
            "no field builder supporting this format has been found ({})".format(
                rems_field.fieldtype
            )
        )

    @staticmethod
    def build_field(rems_field):
        fb = FieldBuilder.build_field_builder(rems_field)
        return fb.build()

    @staticmethod
    @abstractmethod
    def build(rems_field):
        pass

    @classmethod
    def can_handle(cls, rems_field):
        return rems_field.fieldtype in cls.SUPPORTED_FIELD_TYPE

    def __init__(self, rems_field):
        self.rems_field = rems_field
        self.validators = self.get_validators()
        self.label = self.get_label()
        self.render_kw = self.get_render_keywords()

    def get_label(self):
        return self.rems_field.fieldtitle["en"]

    def get_validators(self):
        validators = []
        optional = self.rems_field.fieldoptional
        if optional:
            validators.append(Optional())
        else:
            validators.append(DataRequired())
        max_length = self.rems_field.fieldmax_length
        if max_length:
            validators.append(Length(max=max_length))
        return validators

    def get_render_keywords(self):
        render_kw = {}
        if self.rems_field.fieldplaceholder:
            placeholder = self.rems_field.fieldplaceholder["en"]
            if placeholder:
                render_kw["placeholder"] = placeholder
        return render_kw

    def transform_value(self, value, rems_connector=None, application_id=None):
        return value


class StringFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["text", "description"]

    def build(self):
        return StringField(
            self.label, validators=self.validators, render_kw=self.render_kw
        )


class LabelFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["label"]

    def get_render_keywords(self):
        return {"label": True}

    def build(self):
        return StringField(self.label, validators=[], render_kw=self.render_kw)


class HeaderFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["header"]

    def get_render_keywords(self):
        return {"header": True}

    def build(self):
        return StringField(self.label, validators=[], render_kw=self.render_kw)


class TextAreaFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["texta"]

    def build(self):
        return TextAreaField(
            self.label, validators=self.validators, render_kw=self.render_kw
        )


class AttachmentFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["attachment"]

    def get_validators(self):
        validators = super().get_validators()
        supported_suffixes = ["jpg", "png", "pdf", "docx", "doc"]
        validators.append(
            FileAllowed(
                supported_suffixes,
                f"File extension not in {', '.join(supported_suffixes)}",
            )
        )
        return validators

    def build(self):
        return FileField(
            self.label, validators=self.validators, render_kw=self.render_kw
        )

    def transform_value(self, value, rems_connector=None, application_id=None):
        file = request.files[self.rems_field.fieldid]
        if not file.filename:
            return ""
        temp_dir = tempfile.mkdtemp()
        tmp_file_path = os.path.join(temp_dir, file.filename)
        file.save(tmp_file_path)
        attachment_id = rems_connector.add_attachment(application_id, tmp_file_path)
        return str(attachment_id)


class DateFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["date"]

    def get_render_keywords(self):
        kw = super().get_render_keywords()
        kw["placeholder"] = "YYYY-MM-DD"
        return kw

    def build(self):
        return DateField(
            self.label, validators=self.validators, render_kw=self.render_kw
        )

    def transform_value(self, value, rems_connector=None, application_id=None):
        if value is None:
            return ""
        return value.isoformat()


class SelectFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["option"]

    def build(self):
        choices = []
        for option in self.rems_field.fieldoptions:
            choices.append((option.key, option.label["en"]))
        return SelectField(
            self.label,
            choices=choices,
            validators=self.validators,
            render_kw=self.render_kw,
        )


class MultiSelectFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["multiselect"]

    def build(self):
        choices = []
        for option in self.rems_field.fieldoptions:
            choices.append((option.key, option.label["en"]))
        return MultiCheckboxField(
            self.label,
            choices=choices,
            validators=self.validators,
            render_kw=self.render_kw,
        )

    def transform_value(self, value, rems_connector=None, application_id=None):
        return " ".join(value)


class EmailFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["email"]

    def get_validators(self):
        validators = super().get_validators()
        validators.append(Email())
        return validators

    def build(self):
        return EmailField(
            self.label, validators=self.validators, render_kw=self.render_kw
        )


class TableFieldBuilder(FieldBuilder):
    SUPPORTED_FIELD_TYPE = ["table"]

    def build(self):
        if not self.rems_field.fieldcolumns:
            return TextAreaField(
                self.label, validators=self.validators, render_kw={"rows": 8}
            )

        class TableWtfForm(FlaskForm):
            pass

        for column in self.rems_field.fieldcolumns:
            column_key = column.get("key", "")
            field = StringField(
                column.get("label", {}).get("en", column_key),
                validators=(
                    [Optional()] if self.rems_field.fieldoptional else [DataRequired()]
                ),
                render_kw={
                    "class": "form-control",
                    "style": "padding: 8px 12px !important;",
                },
            )
            setattr(TableWtfForm, column_key, field)

        return FieldList(
            FormField(TableWtfForm, label=""),
            min_entries=1,
            label="",
            render_kw={
                "class": "table-field-container",
                "style": "list-style: none; padding: 10px;",
            },
        )

    def transform_value(self, value, rems_connector=None, application_id=None):
        if not isinstance(value, list):
            return ""

        # REMS SaveDraftCommandFieldValues
        result = []
        for row in value:
            if not isinstance(row, dict):
                continue
            row_data = [
                {"column": k, "value": v}
                for k, v in row.items()
                if k != "csrf_token" and v
            ]
            result.append(row_data)
        return result
